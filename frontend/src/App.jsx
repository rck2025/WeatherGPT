import { useState } from 'react'
import { sendChatMessage } from './api.js'
import { Map, LineChart, History, Terminal, TriangleAlert, Database, Settings, Power } from 'lucide-react'
import WeatherMap from './WeatherMap.jsx'
import ChatWindow from './ChatWindow.jsx'
import AccessibilityMenu from './components/AccessibilityMenu.jsx'

function App() {
  const [isAlertActive, setIsAlertActive] = useState(true)
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Namaste. WeatherGPT online. Ask about weather conditions, alerts, or forecasts.' }
  ])
  const [weatherData, setWeatherData] = useState(null)
  const [mapCenter, setMapCenter] = useState([22.5726, 88.3639]) // Kolkata default
  const [alerts, setAlerts] = useState([])
  const [isLoading, setIsLoading] = useState(false)

  const handleSendMessage = async (queryText) => {
    const userMessage = { role: 'user', text: queryText }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const data = await sendChatMessage(queryText)
      setMessages((prev) => [...prev, { role: 'ai', text: data.bot_reply, sources: data.sources }])
      if (data.weather?.current) setWeatherData(data.weather.current)
      if (data.location?.latitude && data.location?.longitude) {
        setMapCenter([data.location.latitude, data.location.longitude])
      }
      if (data.alerts) setAlerts(data.alerts)
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'ai', text: `[ERROR] Could not reach backend: ${err.message}` }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-[#121414] text-[#e3e2e2] scanline-overlay" style={{ fontFamily: 'Public Sans, sans-serif' }}>

      {/* Top Bar */}
      <header className="flex justify-between items-center h-12 px-4 bg-[#0d0e0f] border-b border-[#333535] flex-shrink-0">
        <div className="flex items-center gap-6">
          <span className="font-bold text-lg text-[#ffc082]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
            WEATHERGPT TERMINAL
          </span>
          <nav className="hidden md:flex gap-4">
            <a className="text-xs font-bold tracking-wider text-[#ffc082] border-b border-[#ffc082] pb-1" href="#" style={{ fontFamily: 'JetBrains Mono, monospace' }}>GLOBAL</a>
            <a className="text-xs font-bold tracking-wider text-[#dbc2ad] pb-1" href="#" style={{ fontFamily: 'JetBrains Mono, monospace' }}>REGIONAL</a>
          </nav>
        </div>
        <div className="flex items-center gap-4 text-[#ffc082]">
          <AccessibilityMenu />
          <Settings size={18} />
          <Power size={18} />
        </div>
      </header>
      <div className="ticker-wrap h-6 flex items-center flex-shrink-0">
<div className="ticker">
{(() => {
const lastAiMessage = [...messages].reverse().find((m) => m.role === 'ai')
if (lastAiMessage) {
return <span className="ticker-item">{lastAiMessage.text.replace(/[#*\n]/g, ' ')}</span>
}
return (
<>
<span className="ticker-item">KOLKATA 32°C ↑</span>
<span className="ticker-item">MUMBAI 28°C ≈</span>
<span className="ticker-item">DELHI 33°C ↑</span>
<span className="ticker-item">CHENNAI 30°C ↓</span>
<span className="ticker-item">BENGALURU 24°C ≈</span>
<span className="ticker-item">HYDERABAD 29°C ↑</span>
</>
)
})()}
</div>
</div>

      {/* Alert Banner (kept from before, restyled) */}
      {isAlertActive && (
        <div className="bg-[#93000a] text-[#ffdad6] py-1.5 px-4 flex justify-between items-center border-b border-[#333535] flex-shrink-0">
          <p className="text-xs font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>⚠ IMD ALERT: Heavy Rainfall Warning (Demo)</p>
          <button onClick={() => setIsAlertActive(false)} className="text-xs">Dismiss</button>
        </div>
      )}

      {/* Main Workspace */}
      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <aside className="flex flex-col items-center py-4 gap-1 bg-[#0d0e0f] border-r border-[#333535] w-16 flex-shrink-0">
  <div className="flex flex-col items-center text-[#dbc2ad] w-full py-2 hover:bg-[#1e2020] hover:text-[#ffc082] transition-colors cursor-pointer">
    <Map size={20} /><span className="text-[8px] mt-1">MAP</span>
  </div>
  <div className="flex flex-col items-center text-[#dbc2ad] w-full py-2 hover:bg-[#1e2020] hover:text-[#ffc082] transition-colors cursor-pointer">
    <LineChart size={20} /><span className="text-[8px] mt-1">FORECAST</span>
  </div>
  <div className="flex flex-col items-center text-[#dbc2ad] w-full py-2 hover:bg-[#1e2020] hover:text-[#ffc082] transition-colors cursor-pointer">
    <History size={20} /><span className="text-[8px] mt-1">HISTORY</span>
  </div>
  <div className="flex flex-col items-center text-[#ffc082] w-full py-2 border-l-2 border-[#ffc082] bg-[#1e2020] cursor-pointer">
    <Terminal size={20} /><span className="text-[8px] mt-1">CHAT</span>
  </div>
  <div className="flex flex-col items-center text-[#dbc2ad] w-full py-2 hover:bg-[#1e2020] hover:text-[#ffc082] transition-colors cursor-pointer">
    <TriangleAlert size={20} /><span className="text-[8px] mt-1">ALERTS</span>
  </div>
  <div className="flex flex-col items-center text-[#dbc2ad] w-full py-2 hover:bg-[#1e2020] hover:text-[#ffc082] transition-colors cursor-pointer">
    <Database size={20} /><span className="text-[8px] mt-1">DATA</span>
  </div>
</aside>

        {/* Content Area */}
        <main className="flex flex-1 p-2 gap-2 bg-black overflow-hidden">
          {/* Chat (60%) */}
          <section className="flex flex-col w-[60%] border border-[#333535] bg-[#121212] rounded-md overflow-hidden">
            <div className="h-5 bg-[#1a1a1a] flex items-center justify-between px-2">
  <span className="text-[10px] font-bold text-[#ffc082]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>AI QUERY BOT</span>
  <span className="flex items-center gap-1">
    <span className="w-1.5 h-1.5 rounded-full bg-[#00FF00] animate-pulse"></span>
    <span className="text-[9px] text-[#00FF00]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>LIVE</span>
  </span>
</div>
            <div className="flex-1 overflow-hidden">
              <ChatWindow messages={messages} onSend={handleSendMessage} isLoading={isLoading} />
            </div>
          </section>

          {/* Right column (40%) */}
          {/* Right column (40%) */}
<section className="flex flex-col w-[40%] gap-1">
  <div className="flex-1 border border-[#333535] bg-[#121212] relative flex flex-col rounded-md overflow-hidden">
    <div className="h-5 bg-[#1a1a1a] flex items-center px-2 flex-shrink-0">
  <span className="text-[10px] font-bold text-[#ffc082]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>REAL-TIME</span>
</div>
<div className="flex-1 relative">
  <WeatherMap center={mapCenter} alerts={alerts} />
  <div className="absolute top-2 right-2 z-[1000] bg-[#333333] text-[#3399FF] text-[10px] font-bold px-2 py-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
    STABLE
  </div>
</div>
  </div>
  <div className="h-[35%] grid grid-cols-2 grid-rows-2 gap-1 flex-shrink-0">
    <div className="border border-[#333535] bg-[#121212] flex flex-col">
      <div className="h-5 bg-[#1a1a1a] flex items-center px-2">
        <span className="text-[10px] text-[#e3e2e2]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>HUMIDITY</span>
      </div>
      <div className="flex-1 flex items-center justify-center">
        <span className="text-[#00FF00] text-2xl font-semibold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
  {weatherData?.humidity != null ? `${weatherData.humidity}%` : '--'}
</span>
      </div>
    </div>
    <div className="border border-[#333535] bg-[#121212] flex flex-col">
      <div className="h-5 bg-[#1a1a1a] flex items-center px-2">
        <span className="text-[10px] text-[#e3e2e2]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>WIND</span>
      </div>
      <div className="flex-1 flex items-center justify-center">
        <span className="text-[#3399FF] text-xl font-semibold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
  {weatherData?.wind_speed != null ? `${weatherData.wind_speed} km/h` : '--'}
</span>
      </div>
    </div>
    <div className="border border-[#333535] bg-[#121212] flex flex-col">
  <div className="h-5 bg-[#1a1a1a] flex items-center px-2">
    <span className="text-[10px] text-[#e3e2e2]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>TEMP</span>
  </div>
  <div className="flex-1 flex items-center justify-center">
    <span className="text-[#00FF00] text-2xl font-semibold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
      {weatherData?.temperature != null ? `${weatherData.temperature}°C` : '--'}
    </span>
  </div>
</div>
    <div className="border border-[#333535] bg-[#121212] flex flex-col">
      <div className="h-5 bg-[#1a1a1a] flex items-center px-2">
        <span className="text-[10px] text-[#e3e2e2]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>PRESSURE</span>
      </div>
      <div className="flex-1 flex items-center justify-center">
        <span className="text-[#e3e2e2] text-xl font-semibold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>1008 hPa</span>
      </div>
    </div>
  </div>
</section>
        </main>
      </div>
      <footer className="flex justify-between items-center px-4 h-6 bg-[#0d0e0f] border-t border-[#333535] text-[10px] text-[#77ff61] flex-shrink-0" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
  <span className="text-[#dbc2ad]">© MINISTRY OF EARTH SCIENCES | OFFICIAL INTEL</span>
  <div className="flex gap-4">
    <span className="text-[#dbc2ad]">UTC: 14:22</span>
    <span className="text-[#dbc2ad]">IST: 19:52</span>
    <span className="text-[#00FF00] font-bold">SYSTEM: OPTIMAL</span>
  </div>
</footer>
    </div>
  )
}

export default App