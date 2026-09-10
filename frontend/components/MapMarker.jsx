import React, { useState } from 'react';

/**
 * Tabler Icon Standalone SVG Fallbacks
 * Ensures icons render instantly even if the external webfont is still loading.
 */
function AlertTriangleIcon({ size = 18, color = '#ffffff' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M5 19h14a2 2 0 0 0 1.84 -2.75l-7.1 -12.25a2 2 0 0 0 -3.5 0l-7.1 12.25a2 2 0 0 0 1.75 2.75" />
    </svg>
  );
}

function CloudRainIcon({ size = 18, color = '#ffffff' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7 18a4.6 4.4 0 0 1 0 -9a5 4.5 0 0 1 11 2h1a3.5 3.5 0 0 1 0 7h-12" />
      <path d="M11 13v2m0 3v2m4 -5v2m0 3v2" />
    </svg>
  );
}

/**
 * MapMarker Component
 * 
 * Clean, icon-only disaster hazard marker. No permanent floating text or glow.
 * Opens safety advisory on tap/click.
 * 
 * @param {Object} props
 * @param {'pressure' | 'rainfall'} props.type - Marker hazard category
 * @param {'moderate' | 'severe' | 'extreme'} [props.severity='severe'] - Hazard severity level
 * @param {string} [props.caption] - Plain-language caption displayed on click
 * @param {string} [props.title] - Headline for popup on click
 * @param {string} [props.actionText] - Action guidance text (e.g., "Stay alert", "Move to safety now")
 * @param {Function} [props.onClick] - Click handler for opening expanded safety advisory
 */
export function MapMarker({
  type = 'pressure',
  severity = 'severe',
  caption = '',
  title = '',
  actionText = '',
  onClick,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const normSeverity = (severity || 'severe').toLowerCase();
  const isModerate = normSeverity === 'moderate';

  const defaultTitle = type === 'pressure' ? 'Storm warning' : 'Active Rainfall Warning';
  const heading = title || defaultTitle;
  const defaultAction = isModerate ? 'Stay alert' : 'Move to safety now';
  const actionGuide = actionText || defaultAction;
  const description = caption || (isModerate ? 'Rain and gusty winds expected nearby' : 'Heavy rain expected nearby');

  const handleClick = (e) => {
    setIsOpen(!isOpen);
    if (onClick) onClick(e);
  };

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      {/* Icon-Only Circular Badge (32px, no floating text, no bleeding glow) */}
      <div
        className={`marker-badge-icon-only severity-${normSeverity} marker-type-${type}`}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        aria-label={`${heading} (${actionGuide}): ${description}`}
        title={`${heading} - Click for safety advice`}
      >
        <i className={`ti ${type === 'pressure' ? 'ti-alert-triangle' : 'ti-cloud-rain'}`} aria-hidden="true">
          {type === 'pressure' ? (
            <AlertTriangleIcon size={18} color="#ffffff" />
          ) : (
            <CloudRainIcon size={18} color="#ffffff" />
          )}
        </i>
      </div>

      {/* Popover / Popup on User Click */}
      {isOpen && (
        <div
          className="plain-safety-popup"
          style={{
            position: 'absolute',
            bottom: '40px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(12, 16, 20, 0.96)',
            border: `1px solid ${isModerate ? '#f0997b' : '#e2504f'}`,
            borderRadius: '6px',
            padding: '10px 12px',
            boxShadow: '0 6px 20px rgba(0,0,0,0.8)',
            zIndex: 1000,
            width: '260px',
            textAlign: 'left',
          }}
        >
          <div className="popup-header-row">
            <span className={`popup-badge ${isModerate ? 'badge-moderate' : 'badge-severe'}`}>
              {isModerate ? 'WATCH // MODERATE' : 'WARNING // SEVERE'}
            </span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setIsOpen(false); }}
              style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '14px' }}
            >
              ✕
            </button>
          </div>
          <div className="popup-title">{heading}</div>
          <div className={`popup-action-guide ${isModerate ? 'guide-moderate' : ''}`}>
            <strong>{actionGuide}</strong>: {isModerate ? 'Keep umbrella ready, secure outdoor items.' : 'Seek shelter inside sturdy buildings immediately.'}
          </div>
          <div className="popup-detail-text">{description}</div>
        </div>
      )}
    </div>
  );
}

export default MapMarker;
