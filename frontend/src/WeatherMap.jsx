import { MapContainer, TileLayer, Marker, Popup, CircleMarker, useMap } from 'react-leaflet'
import { useEffect } from 'react'

const severityColor = (severity) => {
if (severity === 'Extreme' || severity === 'High') return '#FF3131'
if (severity === 'Moderate') return '#FFAC1C'
return '#FFFF00'
}

function RecenterMap({ center }) {
const map = useMap()
useEffect(() => {
map.setView(center, map.getZoom())
}, [center, map])
return null
}

function WeatherMap({ center, alerts = [] }) {
const position = center || [22.5726, 88.3639]

return (
<MapContainer center={position} zoom={11} style={{ height: '100%', width: '100%' }}>
<TileLayer
url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
attribution='&copy; OpenStreetMap contributors'
/>
<RecenterMap center={position} />

<Marker position={position}>
<Popup>Current location</Popup>
</Marker>

{alerts.map((alert, idx) => (
<CircleMarker
key={idx}
center={position}
radius={12}
pathOptions={{
color: severityColor(alert.severity),
fillColor: severityColor(alert.severity),
fillOpacity: 0.5,
}}
className="pulsing-marker"
>
<Popup>
<strong>{alert.title}</strong>
<br />
{alert.description}
<br />
<em>Source: {alert.source}</em>
</Popup>
</CircleMarker>
))}
</MapContainer>
)
}

export default WeatherMap