"""Faithful port of the T-Eval evaluators for the ci-wiki agent.

Source: https://github.com/open-compass/T-Eval
Paper: Chen et al., 'T-Eval: Evaluating the Tool Utilization Capability of
       Large Language Models Step by Step', ACL 2024 (arXiv:2312.14033).

T-Eval decomposes tool utilization into six abilities:
    INSTRUCT, PLAN, REASON, RETRIEVE, UNDERSTAND, REVIEW

Implemented faithfully here are the four evaluator classes that the official
repo ships (the official repo also folds REASON/RETRIEVE/UNDERSTAND into a
single `ReasonRetrieveUnderstandEvaluator`):

    InstructEvaluator         — format_metric + args_em_metric
    PlanningEvaluator         — BERT-score matching (name_weight=0.75,
                                 args_weight=0.25, threshold=0.8) followed
                                 by Hungarian matching + Longest Increasing
                                 Subsequence to count correctly-ordered
                                 nodes; reports precision / recall / f1
    ReasonRetrieveUnderstandEvaluator — thought (cosine BERT-score), name
                                         (exact match), args (key-level
                                         exact-match ratio)
    ReviewEvaluator           — multiple-choice exact match + parse_rate

The default sentence-transformer model is `all-mpnet-base-v2`, identical to
the upstream default.
"""
from __future__ import annotations

import copy
import itertools
import re
from typing import Any

import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer, util


# --------------------------------------------------------------------------- #
# InstructEvaluator (faithful port)
# --------------------------------------------------------------------------- #
class InstructEvaluator:
    """Instruction-following evaluation (format adherence + arg exact match).

    args_em_metric = (action_match + sum_i [pred[k_i] == gt[k_i]]) / (num_gt_args + 1)

    This is identical to T-Eval's compute_args_em_metric.
    """

    def evaluate(self, data_samples: list[dict]) -> dict:
        out = []
        for ds in data_samples:
            response_format = ds.get("response_format", "json")
            pred = ds.get("pred")
            gt = ds.get("gt")

            metrics = {f"{response_format}_format_metric": 0,
                       f"{response_format}_args_em_metric": 0}

            if pred is None or "action" not in pred or "args" not in pred:
                out.append(metrics)
                continue

            metrics[f"{response_format}_format_metric"] = 1
            metrics[f"{response_format}_args_em_metric"] = self._args_em(
                gt["action"], pred["action"], gt["args"], pred["args"]
            )
            out.append(metrics)

        # Aggregate exactly like upstream: rounded mean.
        agg: dict[str, Any] = {}
        keys = set().union(*[m.keys() for m in out])
        for k in keys:
            vals = [m.get(k, 0) for m in out]
            agg[k] = round(float(np.mean(vals)), 4) if vals else 0.0
        return agg

    @staticmethod
    def _args_em(gt_action, pred_action, gt_args, pred_args) -> float:
        cnt = 0.0
        if gt_action == pred_action:
            cnt += 1.0
        num_args = len(gt_args) + 1  # +1 for action name match
        for gt_key, gt_val in gt_args.items():
            if pred_args.get(gt_key, "") == gt_val:
                cnt += 1.0
        return cnt / num_args


# --------------------------------------------------------------------------- #
# PlanningEvaluator (faithful port of bertscore_match + permutation_match)
# --------------------------------------------------------------------------- #
class PlanningEvaluator:
    """Plan-level evaluation using BERT-score matching + Hungarian + LIS.

    Hyperparameters are the upstream defaults:
        name_weight     = 0.75
        args_weight     = 0.25
        match_threshold = 0.8
        bert_score_model = 'all-mpnet-base-v2'
    """

    def __init__(
        self,
        name_weight: float = 0.75,
        args_weight: float = 0.25,
        match_threshold: float = 0.8,
        match_strategy: str = "bertscore",
        bert_score_model: str = "all-mpnet-base-v2",
    ) -> None:
        assert match_strategy in {"bertscore", "permutation"}
        self.name_weight = name_weight
        self.args_weight = args_weight
        self.match_threshold = match_threshold
        self.match_strategy = match_strategy
        self.sentence_model = (
            SentenceTransformer(bert_score_model)
            if match_strategy == "bertscore"
            else None
        )

    def evaluate(self, data_samples: list[dict]) -> dict:
        results = []
        for ds in data_samples:
            pred_plan = ds["pred_plan"]
            gt_plan = ds["gt_plan"]
            if self.match_strategy == "bertscore":
                m = self._bertscore_match(pred_plan, gt_plan)
            else:
                m = self._permutation_match(pred_plan, gt_plan)
            m["parse_rate"] = 0 if (not pred_plan or not gt_plan) else 1
            results.append(m)

        keys = ["precision", "recall", "f1_score", "parse_rate"]
        return {k: float(np.mean([r[k] for r in results])) for k in keys}

    def _bertscore_match(self, pred_plan, gt_plan) -> dict:
        if not pred_plan or not gt_plan:
            return {"precision": 0, "recall": 0, "f1_score": 0}

        pred_plan = copy.deepcopy(sorted(pred_plan, key=lambda x: x["id"]))
        gt_plan = copy.deepcopy(sorted(gt_plan, key=lambda x: x["id"]))

        if pred_plan and pred_plan[-1].get("name") == "FinishAction":
            pred_plan = pred_plan[:-1]
        if gt_plan and gt_plan[-1].get("name") == "FinishAction":
            gt_plan = gt_plan[:-1]

        len_pred, len_gt = len(pred_plan), len(gt_plan)
        if len_pred == 0 or len_gt == 0:
            return {"precision": 0, "recall": 0, "f1_score": 0}

        name_pred = [p["name"] for p in pred_plan]
        args_pred = [str(p["args"]) for p in pred_plan]
        name_gt = [p["name"] for p in gt_plan]
        args_gt = [str(p["args"]) for p in gt_plan]

        name_pe = self.sentence_model.encode(name_pred, convert_to_tensor=True)
        name_ge = self.sentence_model.encode(name_gt, convert_to_tensor=True)
        args_pe = self.sentence_model.encode(args_pred, convert_to_tensor=True)
        args_ge = self.sentence_model.encode(args_gt, convert_to_tensor=True)

        name_cs = np.maximum(util.cos_sim(name_pe, name_ge).cpu().numpy(), 0)
        args_cs = np.maximum(util.cos_sim(args_pe, args_ge).cpu().numpy(), 0)

        score_matrix = name_cs * self.name_weight + args_cs * self.args_weight

        G = nx.Graph()
        for i in range(len_pred):
            for j in range(len_gt):
                if score_matrix[i][j] > self.match_threshold:
                    # Same convention as upstream: int / str labels to avoid
                    # node collision between pred and gt indices.
                    G.add_edge(i, str(j), weight=score_matrix[i][j])
        matching = nx.max_weight_matching(G)

        pred_to_gt = {}
        for a, b in matching:
            if isinstance(a, int):
                pred_to_gt[a] = int(b)
            else:
                pred_to_gt[int(b)] = int(a)
        for i in range(len_pred):
            pred_to_gt.setdefault(i, -1)

        # Longest Increasing Subsequence over pred_to_gt mapping
        dp = np.ones(len_pred)
        for i in range(len_pred):
            for j in range(i):
                if pred_to_gt[i] == -1 or pred_to_gt[j] == -1:
                    continue
                if pred_to_gt[i] > pred_to_gt[j]:
                    dp[i] = max(dp[i], dp[j] + 1)
        correct = int(max(dp)) if len_pred else 0

        recall = correct / len_gt
        precision = correct / len_pred
        f1 = (2 * recall * precision / (recall + precision)) if (recall + precision) else 0
        return {"precision": precision, "recall": recall, "f1_score": f1}

    @staticmethod
    def _permutation_match(pred_plan, gt_plan) -> dict:
        # Cap length at 9 to keep permutation tractable, identical to upstream.
        pred_plan = copy.deepcopy(pred_plan[:9])
        gt_plan = copy.deepcopy(gt_plan[:9])
        len_pred, len_gt = len(pred_plan), len(gt_plan)

        for i in range(len_gt):
            gt_plan[i].setdefault("prev", []).append(i)
        for i in range(len_pred):
            pred_plan[i].setdefault("prev", []).append(i)

        gt_prev_count = sum(len(p["prev"]) for p in gt_plan)
        pred_prev_count = sum(len(p["prev"]) for p in pred_plan)
        if gt_prev_count == 0 or pred_prev_count == 0:
            return {"precision": 0, "recall": 0, "f1_score": 0}

        max_recall = max_precision = max_f1 = 0.0
        nums = range(max(len_pred, len_gt))
        for perm in itertools.permutations(nums, len_pred):
            correct = 0
            for i in range(len_pred):
                if perm[i] >= len_gt:
                    continue
                for j in pred_plan[i]["prev"]:
                    if perm[j] in gt_plan[perm[i]]["prev"]:
                        correct += 1
            r = correct / gt_prev_count
            p = correct / pred_prev_count
            if r + p == 0:
                continue
            f1 = 2 * r * p / (r + p)
            if f1 > max_f1:
                max_f1, max_recall, max_precision = f1, r, p
        return {"precision": max_precision, "recall": max_recall, "f1_score": max_f1}


# --------------------------------------------------------------------------- #
# ReasonRetrieveUnderstandEvaluator (faithful port)
# --------------------------------------------------------------------------- #
class ReasonRetrieveUnderstandEvaluator:
    """Evaluates reasoning thought / tool name retrieval / arg understanding.

    Identical to upstream:
        thought   -> cosine similarity of sentence-transformer embeddings
                     (clamped at 0)
        name      -> exact-string match
        args      -> per-key exact match, ratio over (len(gt_args) + 1e-5)
                     with special-cases:
                         len(gt)==0 and len(pred)==0 -> 1.0
                         len(gt)==0 and len(pred)!=0 -> 0.0
        parse_rate-> 1 if pred parsed to a dict with the required keys
    """

    def __init__(self, bert_score_model: str = "all-mpnet-base-v2") -> None:
        self.sentence_model = SentenceTransformer(bert_score_model)

    def evaluate(self, data_samples: list[dict]) -> dict:
        per_sample = []
        for ds in data_samples:
            pred = ds.get("pred", {}) or {}
            gt = ds.get("gt", {}) or {}
            m = {"thought": 0.0, "name": 0.0, "args": 0.0, "parse_rate": 0.0}
            if pred:
                m["parse_rate"] = 1.0

            if "thought" in pred and "thought" in gt:
                pe = self.sentence_model.encode(pred["thought"], convert_to_tensor=True)
                ge = self.sentence_model.encode(gt["thought"], convert_to_tensor=True)
                m["thought"] = float(max(util.cos_sim(pe, ge).cpu().numpy().item(), 0.0))

            if "name" in pred and "name" in gt:
                m["name"] = 1.0 if pred["name"] == gt["name"] else 0.0

            if "args" in pred and "args" in gt:
                if isinstance(gt["args"], dict):
                    if len(gt["args"]) == 0 and len(pred["args"]) == 0:
                        m["args"] = 1.0
                    elif len(gt["args"]) == 0 and len(pred["args"]) != 0:
                        m["args"] = 0.0
                    else:
                        matches = 0
                        for k, v in gt["args"].items():
                            if k in pred["args"] and str(pred["args"][k]) == str(v):
                                matches += 1
                        m["args"] = matches / (len(gt["args"]) + 1e-5)
                else:
                    pa = str(pred["args"]).strip("'").strip('"')
                    m["args"] = 1.0 if str(gt["args"]) == pa else 0.0

            per_sample.append(m)

        return {k: float(np.mean([r[k] for r in per_sample]))
                for k in ["thought", "name", "args", "parse_rate"]}


# --------------------------------------------------------------------------- #
# ReviewEvaluator (faithful port)
# --------------------------------------------------------------------------- #
class ReviewEvaluator:
    """Review (multiple-choice / verification) ability.

    review_quality = 1 if pred == gt else 0
    parse_rate     = 1 if pred is not None else 0
    """

    def evaluate(self, data_samples: list[dict]) -> dict:
        per = []
        for ds in data_samples:
            pred = ds.get("pred")
            gt = ds.get("gt")
            r = {"parse_rate": 0.0, "review_quality": 0.0}
            if pred is not None:
                r["parse_rate"] = 1.0
                r["review_quality"] = 1.0 if pred == gt else 0.0
            per.append(r)
        return {
            "parse_rate": float(np.mean([r["parse_rate"] for r in per])),
            "review_quality": float(np.mean([r["review_quality"] for r in per])),
        }
