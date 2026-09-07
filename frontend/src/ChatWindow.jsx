import { useRef, useEffect, useState } from 'react'

function ChatWindow({ messages, onSend, isLoading }) {
const [input, setInput] = useState('')
const scrollRef = useRef(null)

useEffect(() => {
scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
}, [messages])

const handleSend = () => {
if (!input.trim() || isLoading) return
onSend(input)
setInput('')
}

return (
<div className="flex flex-col h-full bg-[#121212] text-[#e3e2e2]" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' }}>
<div className="flex-1 p-2 overflow-y-auto flex flex-col gap-3">
{messages.map((msg, idx) => (
msg.role === 'user' ? (
<div key={idx} className="bg-[#1a1410] border-l-2 border-[#ffc082] pl-2 py-1">
<span className="text-[#ffc082] font-bold">USER&gt;</span> {msg.text}
</div>
) : (
<div key={idx} className="bg-[#0a0a0a] border border-[#333333] p-2">
<div className="text-[#ffc082] font-bold mb-1">PROMPT&gt; AI_RESPONSE</div>
<div className="text-[#00FF00] whitespace-pre-wrap">{msg.text}</div>
{msg.sources && msg.sources.length > 0 && (
<div className="mt-2 flex flex-wrap gap-1">
{msg.sources.map((src, sIdx) => (
<span
key={sIdx}
title={src.content}
className="text-[9px] bg-[#333333] text-[#3399FF] px-2 py-0.5 cursor-help"
>
{src.source}
</span>
))}
</div>
)}
</div>
)
))}
{isLoading && (
<div className="text-[#ffc082] text-xs">PROMPT&gt; AI_ANALYSIS_IN_PROGRESS...</div>
)}
<div ref={scrollRef} />
</div>
<div className="p-2 border-t border-[#333333] bg-black">
<div className="flex items-center border-b border-[#FF9900] pb-1">
<span className="text-[#ffc082] font-bold mr-2">CMD&gt;</span>
<input
type="text"
className="flex-1 bg-transparent border-none outline-none text-[#e3e2e2]"
placeholder="Ask about the weather..."
value={input}
onChange={(e) => setInput(e.target.value)}
onKeyDown={(e) => e.key === 'Enter' && handleSend()}
disabled={isLoading}
/>
<span className="text-[#00FF00] font-bold cursor-blink">|</span>
</div>
</div>
</div>
)
}

export default ChatWindow