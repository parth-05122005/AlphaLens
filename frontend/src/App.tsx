import { Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'

function Home() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => (await api.get('/health/')).data as { status: string; db: boolean; redis: boolean },
  })
  return (
    <div className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">AlphaLens</h1>
      <p className="mt-2 text-slate-600">AI research copilot for your portfolio.</p>
      <pre className="mt-6 rounded-lg bg-white p-4 text-sm shadow-sm">
        {health.isLoading ? 'Checking API…' : JSON.stringify(health.data ?? health.error?.message, null, 2)}
      </pre>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
