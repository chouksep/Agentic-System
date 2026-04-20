import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { LogOut, Menu, X } from 'lucide-react'
import { useState } from 'react'

export default function Navigation() {
  const navigate = useNavigate()
  const clearAuth = useAuthStore((state) => state.clearAuth)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <nav className="bg-slate-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/dashboard" className="flex items-center font-bold text-xl">
            🎤 Speaking Coach
          </Link>

          {/* Desktop Menu */}
          <div className="hidden md:flex gap-8">
            <Link to="/dashboard" className="hover:text-blue-400 transition">
              Dashboard
            </Link>
            <Link to="/profiles" className="hover:text-blue-400 transition">
              Profiles
            </Link>
            <Link to="/analytics" className="hover:text-blue-400 transition">
              Analytics
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden"
          >
            {mobileMenuOpen ? <X /> : <Menu />}
          </button>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            className="hidden md:flex items-center gap-2 bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition"
          >
            <LogOut size={20} />
            Logout
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden pb-4 space-y-2">
            <Link
              to="/dashboard"
              className="block hover:text-blue-400 transition py-2"
            >
              Dashboard
            </Link>
            <Link
              to="/profiles"
              className="block hover:text-blue-400 transition py-2"
            >
              Profiles
            </Link>
            <Link
              to="/analytics"
              className="block hover:text-blue-400 transition py-2"
            >
              Analytics
            </Link>
            <button
              onClick={handleLogout}
              className="w-full text-left flex items-center gap-2 bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition"
            >
              <LogOut size={20} />
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}
