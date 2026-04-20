import { useParams } from 'react-router-dom'

export default function CallInterface() {
  const { callId } = useParams()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-8">Call Interface</h1>
        <div className="bg-slate-800 rounded-lg shadow-xl p-8 text-center">
          <p className="text-xl text-slate-400 mb-4">Call ID: {callId}</p>
          <p className="text-lg text-slate-300">
            Real-time call interface with Twilio integration and voice analysis coming in Phase 1
          </p>
        </div>
      </div>
    </div>
  )
}
