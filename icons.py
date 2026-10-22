#
# toolbar and menu icons, drawn from small inline SVGs so they look
# the same on every platform and stay sharp on high dpi screens
#
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

STROKE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'''

BODIES = {
	"new": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
		'<path d="M14 3v6h6"/><path d="M12 12v6M9 15h6"/>',
	"open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1"/>'
		'<path d="M3 7v11a2 2 0 0 0 2 2h13.5a2 2 0 0 0 1.9-1.4L22.5 12H7.2a2 2 0 0 0-1.9 1.4L3 20"/>',
	"save": '<path d="M5 3h11l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
		'<path d="M7 3v5h8V3"/><rect x="7" y="13" width="10" height="8"/>',
	"saveas": '<path d="M12 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v3"/>'
		'<path d="M7 3v5h8V3"/><path d="M7 21v-6h5"/>'
		'<path d="M20.5 14.5l1 1-5.5 5.5H15v-1z"/>',
	"backup": '<rect x="3" y="4" width="18" height="5" rx="1"/>'
		'<path d="M5 9v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9"/><path d="M10 13h4"/>',
	"recent": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
	"book": '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/>'
		'<path d="M4 21.5A2.5 2.5 0 0 1 6.5 19H20v3H6.5"/>',
	"graphics": '<rect x="3" y="4" width="18" height="16" rx="2"/>'
		'<path d="M7 16l3-4 3 2 4-6"/>',
	"filter": '<path d="M3 4h18l-7 8v6l-4 2v-8z"/>',
	"stats": '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
	"find": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>',
	"quit": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
}

COLORS = {"backup": "#7a4fb5", "save": "#1f6fd1", "saveas": "#1f6fd1", "new": "#2e8b57", "open": "#c98a00"}

_cache = {}

def icon(name, color=None):
	"""the named icon as a QIcon, drawn at a few sizes"""
	color = color or COLORS.get(name, "#444444")
	key = (name, color)
	if key in _cache:
		return _cache[key]
	svg = STROKE.format(color=color, body=BODIES[name])
	r = QSvgRenderer(QByteArray(svg.encode()))
	ic = QIcon()
	for size in (16, 24, 32, 48, 64):
		pm = QPixmap(size, size)
		pm.fill(Qt.GlobalColor.transparent)
		p = QPainter(pm)
		p.setRenderHint(QPainter.RenderHint.Antialiasing)
		r.render(p, QRectF(0, 0, size, size))
		p.end()
		ic.addPixmap(pm)
	_cache[key] = ic
	return ic
