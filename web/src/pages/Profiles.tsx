import { useQuery } from 'react-query'
import { profilesAPI } from '@/services/api'
import { useState } from 'react'

export default function Profiles() {
  const { data: profiles } = useQuery('profiles', () => profilesAPI.list())
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    profile_type: 'interview',
    coaching_focus: {},
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await profilesAPI.create(formData)
      setShowForm(false)
      setFormData({ name: '', profile_type: 'interview', coaching_focus: {} })
    } catch (err) {
      alert('Failed to create profile')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-slate-900 mb-8">Coaching Profiles</h1>

        <div className="mb-8">
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg transition"
          >
            {showForm ? 'Cancel' : 'Create Profile'}
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-8">
            <h2 className="text-2xl font-semibold text-slate-900 mb-4">New Profile</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
                <select
                  value={formData.profile_type}
                  onChange={(e) => setFormData({ ...formData, profile_type: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="interview">Interview</option>
                  <option value="sales">Sales</option>
                  <option value="presentation">Presentation</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg transition"
              >
                Create
              </button>
            </form>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {profiles?.data?.map((profile: any) => (
            <div key={profile.id} className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-xl font-semibold text-slate-900 mb-2">{profile.name}</h3>
              <p className="text-slate-600 mb-4 capitalize">{profile.profile_type}</p>
              <button className="text-blue-600 hover:text-blue-700 font-semibold">Edit</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
