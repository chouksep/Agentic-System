import { useQuery } from 'react-query'
import { useNavigate } from 'react-router-dom'
import { callsAPI, analyticsAPI, profilesAPI } from '@/services/api'
import { Phone } from 'lucide-react'
import { useState } from 'react'

export default function Dashboard() {
  const navigate = useNavigate()
  const [selectedProfile, setSelectedProfile] = useState('')
  const { data: calls } = useQuery('calls', () => callsAPI.list(10))
  const { data: analytics } = useQuery('analytics', () => analyticsAPI.getSummary())
  const { data: profiles } = useQuery('profiles', () => profilesAPI.list())

  const handleStartCall = async () => {
    if (!selectedProfile) {
      alert('Please select a coaching profile')
      return
    }
    try {
      const response = await callsAPI.start(selectedProfile, 'phone')
      navigate(`/call/${response.data.call_id}`)
    } catch (err) {
      alert('Failed to start call')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-slate-900 mb-8">Welcome to Speaking Coach</h1>

        {/* Start Call Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-2xl font-semibold text-slate-900 mb-4">Start a Call</h2>
          <div className="flex gap-4">
            <select
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(e.target.value)}
              className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a coaching profile...</option>
              {profiles?.data?.map((profile: any) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleStartCall}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg flex items-center gap-2 transition"
            >
              <Phone size={20} />
              Start Call
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Analytics Cards */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-sm font-semibold text-slate-600 mb-2">Total Calls</h3>
            <p className="text-3xl font-bold text-slate-900">{analytics?.data?.total_calls || 0}</p>
          </div>
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-sm font-semibold text-slate-600 mb-2">Total Minutes</h3>
            <p className="text-3xl font-bold text-slate-900">
              {Math.round(analytics?.data?.total_minutes || 0)}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-sm font-semibold text-slate-600 mb-2">Avg. Pace</h3>
            <p className="text-3xl font-bold text-slate-900">
              {analytics?.data?.avg_pace?.toFixed(0) || '-'}
            </p>
          </div>
        </div>

        {/* Recent Calls */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-2xl font-semibold text-slate-900 mb-4">Recent Calls</h2>
          {calls?.data && calls.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 px-4 font-semibold text-slate-700">Date</th>
                    <th className="text-left py-2 px-4 font-semibold text-slate-700">Duration</th>
                    <th className="text-left py-2 px-4 font-semibold text-slate-700">Type</th>
                    <th className="text-left py-2 px-4 font-semibold text-slate-700">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.data.map((call: any) => (
                    <tr key={call.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-3 px-4">{new Date(call.started_at).toLocaleDateString()}</td>
                      <td className="py-3 px-4">{call.duration_seconds}s</td>
                      <td className="py-3 px-4">{call.call_type}</td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => navigate(`/call/${call.id}`)}
                          className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-slate-600">No calls yet. Start your first call to get started!</p>
          )}
        </div>
      </div>
    </div>
  )
}
