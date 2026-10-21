// ═══════════════════════════════════════════════════
// map.js — 线段碰撞检测（路线用线段而非散点）
// ═══════════════════════════════════════════════════

var map = L.map('map', { center: [{{CENTER_LAT}}, {{CENTER_LNG}}], zoom: 7, zoomControl: true, scrollWheelZoom: true, attributionControl: true });
window.routeMap = map;
var tileAttribution = '&copy; <a href="https://www.esri.com/">Esri</a>';
var standardTile = L.tileLayer('{{TILE_URL}}', { attribution: tileAttribution, maxZoom: 20, className: 'tile-standard' });
var standardTransport = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, opacity: 0.36, className: 'tile-transport' });
var terrainTile = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', { attribution: tileAttribution, maxZoom: 17, className: 'tile-terrain' });
standardTile.addTo(map);
standardTransport.addTo(map);
document.querySelectorAll('.ls-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.ls-btn').forEach(function(b) {
      b.classList.remove('active');
      b.setAttribute('aria-pressed', 'false');
    });
    this.classList.add('active');
    this.setAttribute('aria-pressed', 'true');
    if (this.dataset.layer === 'standard') {
      map.removeLayer(terrainTile);
      standardTile.addTo(map);
      standardTransport.addTo(map);
    } else {
      map.removeLayer(standardTile);
      map.removeLayer(standardTransport);
      terrainTile.addTo(map);
    }
  });
});

// ── 文字测量 ──
var _mc = null, _mx = null;
function mw(txt, s) {
  if (!_mx) { _mc = document.createElement('canvas'); _mx = _mc.getContext('2d'); }
  _mx.font = s + 'px "Noto Sans SC", system-ui, sans-serif';
  return Math.round(_mx.measureText(txt).width);
}

// ── 路线（主路线 + 支线 + 端线段数据）──
for (var i = 0; i < mainRoutes.length; i++)
  L.polyline(mainRoutes[i][1], {
    color: mainRoutes[i][0],
    weight: 4,
    opacity: mainRoutes[i][2] === 'estimated' ? 0.65 : 0.85,
    dashArray: mainRoutes[i][2] === 'estimated' ? '8,6' : null,
    smoothFactor: 1
  }).addTo(map);
var spurLayer = L.layerGroup();

// 预采样路线线段（每 5 个点取一段），用于像素碰撞
var routeSegData = [];
function collectSegs(arr) {
  for (var i = 0; i < arr.length; i++) {
    var poly = arr[i][1];
    for (var j = 0; j + 1 < poly.length; j += 5)
      routeSegData.push([poly[j], poly[j+1]]);
  }
}
collectSegs(mainRoutes);
collectSegs(spurRoutes);

// ── 线段-矩形 相交检测 ──
function segHitRect(x1,y1,x2,y2,l,r,t,b) {
  function inside(px,py) { return px>=l&&px<=r&&py>=t&&py<=b; }
  if (inside(x1,y1)||inside(x2,y2)) return true;
  function segInt(ax1,ay1,ax2,ay2,bx1,by1,bx2,by2) {
    var dx1=ax2-ax1,dy1=ay2-ay1,dx2=bx2-bx1,dy2=by2-by1;
    var cr = dx1*dy2-dy1*dx2;
    if (Math.abs(cr)<1e-9) return false;
    var t2=((bx1-ax1)*dy2-(by1-ay1)*dx2)/cr;
    var u=((bx1-ax1)*dy1-(by1-ay1)*dx1)/cr;
    return t2>=0&&t2<=1&&u>=0&&u<=1;
  }
  return segInt(x1,y1,x2,y2,l,t,r,t)||segInt(x1,y1,x2,y2,l,b,r,b)||
         segInt(x1,y1,x2,y2,l,t,l,b)||segInt(x1,y1,x2,y2,r,t,r,b);
}

// ── 城市圆点 ──
var dotLayer = L.layerGroup().addTo(map);
for (var i = 0; i < cityPosData.length; i++) {
  var c = cityPosData[i];
  dotLayer.addLayer(L.circleMarker([c.lat, c.lng], { radius: 5, color: c.color, weight: 2.5, fillColor: '#fff', fillOpacity: 1 }));
}

// ── 标签图层 ──
var labelLayer = L.layerGroup().addTo(map);
var leadLayer = L.layerGroup().addTo(map);

// ── POI ──
var poiMajor = L.layerGroup();
var poiMinor = L.layerGroup();
for (var i = 0; i < majorSpots.length; i++) {
  var s = majorSpots[i];
  var dir = s[5] < 0 ? 'top' : (s[5] > 0 ? 'bottom' : (s[4] < 0 ? 'left' : 'right'));
  var dot = L.circleMarker([s[0], s[1]], { radius: 4, color: s[2], weight: 2, fillColor: '#fff', fillOpacity: 1 });
  dot.bindTooltip(s[3], {
    permanent: true,
    direction: dir,
    className: 'poi-tooltip',
    opacity: 1
  });
  poiMajor.addLayer(dot);
}
for (var i = 0; i < spots.length; i++) {
  var s = spots[i];
  var dot = L.circleMarker([s[0], s[1]], { radius: 3, color: '#3d7a4a', weight: 2, fillColor: '#fff', fillOpacity: 1 });
  dot.bindTooltip(s[2], {
    permanent: true,
    direction: 'right',
    className: 'poi-tooltip poi-tooltip-minor',
    opacity: 1
  });
  poiMinor.addLayer(dot);
}

// ── 配置 ──
var CFG = [
  { zMin:0, zMax:99, basePx:28, compact:true, lead:true },
];
var DIRS = [[1,0],[-1,0],[0,-1],[0,1],[1,-1],[-1,-1],[1,1],[-1,1]];

// ── 碰撞检测（线段级：城市全检 / Dx不检路线）──
function hasOverlap(cx, cy, w, h, segPx, dp, boxes, checkRoutes) {
  var hw = w/2, hh = h/2, l=cx-hw, r=cx+hw, t=cy-hh, b=cy+hh;
  if (checkRoutes) {
    for (var i=0;i<segPx.length;i++)
      if (segHitRect(segPx[i].x1,segPx[i].y1,segPx[i].x2,segPx[i].y2,l,r,t,b)) return true;
  }
  // 圆点
  for (var i=0;i<dp.length;i++)
    if (dp[i].x>=l-7&&dp[i].x<=r+7&&dp[i].y>=t-7&&dp[i].y<=b+7) return true;
  // 已放标签
  for (var i=0;i<boxes.length;i++) {
    var o=boxes[i];
    if (l<o.r&&r>o.l&&t<o.b&&b>o.t) return true;
  }
  return false;
}

// ── 搜索无碰撞位置 ──
// 逐级半径，每级 8 方向全试，选离路线最远的那个
// checkRoutes: true=城市+DC（全检）, false=Dx（不检路线）
function _posScore(cx,cy,segPx,dp,boxes,checkRoutes) {
  // 返回 {segDist, dotDist, boxDist} 评分用
  var r = {segDist:Infinity, dotDist:Infinity, boxDist:Infinity};
  if (checkRoutes)
    for (var i=0;i<segPx.length;i++) {
      var mx=(segPx[i].x1+segPx[i].x2)/2, my=(segPx[i].y1+segPx[i].y2)/2;
      var dd=(cx-mx)*(cx-mx)+(cy-my)*(cy-my);
      if (dd<r.segDist) r.segDist=dd;
    }
  for (var i=0;i<dp.length;i++) {
    var dd=(cx-dp[i].x)*(cx-dp[i].x)+(cy-dp[i].y)*(cy-dp[i].y);
    if (dd<r.dotDist) r.dotDist=dd;
  }
  for (var i=0;i<boxes.length;i++) {
    var o=boxes[i];
    if (cx>=o.l-4&&cx<=o.r+4&&cy>=o.t-4&&cy<=o.b+4) { r.boxDist=0; break; }
    var dx=Math.max(0,o.l-cx,cx-o.r), dy=Math.max(0,o.t-cy,cy-o.b);
    var dd=dx*dx+dy*dy;
    if (dd<r.boxDist) r.boxDist=dd;
  }
  return r;
}
function findPos(lat,lng,basePx,w,h,segPx,dp,boxes,checkRoutes) {
  var org = map.latLngToLayerPoint(L.latLng(lat,lng));
  var hw = w/2, hh = h/2;
  var sc = [1,1.5,2,2.5,3];
  for (var si=0;si<sc.length;si++) {
    var d = basePx*sc[si];
    var best=null, bestS={segDist:0,dotDist:0,boxDist:0};
    for (var di=0;di<DIRS.length;di++) {
      var cx=org.x+DIRS[di][0]*d, cy=org.y+DIRS[di][1]*d;
      if (!hasOverlap(cx,cy,w,h,segPx,dp,boxes,checkRoutes)) {
        var s = _posScore(cx,cy,segPx,dp,boxes,checkRoutes);
        // 同半径内比谁离路线更远 > 离圆点更远 > 离标签更远
        if (!best || s.segDist>bestS.segDist ||
            (s.segDist==bestS.segDist && s.dotDist>bestS.dotDist) ||
            (s.segDist==bestS.segDist && s.dotDist==bestS.dotDist && s.boxDist>bestS.boxDist)) {
          best = {cx:cx,cy:cy};
          bestS = s;
        }
      }
    }
    if (best) {
      var ll = map.layerPointToLatLng(L.point(best.cx,best.cy));
      return {lat:ll.lat,lng:ll.lng,box:{l:best.cx-hw,r:best.cx+hw,t:best.cy-hh,b:best.cy+hh}};
    }
  }
  // fallback: 4×–10× basePx 逐级搜（几不可达）
  for (var si=4;si<=10;si++) {
    var d = basePx*si;
    var best=null, bestS={segDist:0,dotDist:0,boxDist:0};
    for (var di=0;di<DIRS.length;di++) {
      var cx=org.x+DIRS[di][0]*d, cy=org.y+DIRS[di][1]*d;
      if (!hasOverlap(cx,cy,w,h,segPx,dp,boxes,checkRoutes)) {
        var s = _posScore(cx,cy,segPx,dp,boxes,checkRoutes);
        if (!best || s.segDist>bestS.segDist ||
            (s.segDist==bestS.segDist && s.dotDist>bestS.dotDist) ||
            (s.segDist==bestS.segDist && s.dotDist==bestS.dotDist && s.boxDist>bestS.boxDist)) {
          best = {cx:cx,cy:cy};
          bestS = s;
        }
      }
    }
    if (best) {
      var ll = map.layerPointToLatLng(L.point(best.cx,best.cy));
      return {lat:ll.lat,lng:ll.lng,box:{l:best.cx-hw,r:best.cx+hw,t:best.cy-hh,b:best.cy+hh}};
    }
  }
  return {lat:lat,lng:lng,box:{l:0,r:0,t:0,b:0}};
}

// ── 标签工厂 ──
function mkCity(lat,lng,color,name) {
  return L.marker([lat,lng],{icon:L.divIcon({className:'',html:'<span style="display:inline-block;color:'+color+';font-size:14px;font-weight:700;white-space:nowrap;text-shadow:0 0 4px #fff,0 0 8px #fff;">'+name+'</span>',iconSize:null,iconAnchor:[Math.round(mw(name,14)/2),10]})});
}
function mkDx(lat,lng,color,name,sub,dist) {
  var lbl='<div style="text-align:center;line-height:1.3;white-space:nowrap;"><div style="font-weight:700;font-size:12px;color:'+color+';text-shadow:0 0 4px #fff,0 0 8px #fff;">'+name+'</div>';
  if (sub) lbl+='<div style="font-size:10px;color:'+color+';text-shadow:0 0 4px #fff,0 0 8px #fff;">'+sub+'</div>';
  lbl+='<div style="font-size:10px;color:#7a7258;text-shadow:0 0 4px #fff,0 0 8px #fff;">'+dist+'</div></div>';
  return L.marker([lat,lng],{icon:L.divIcon({className:'',html:lbl,iconSize:[80,36],iconAnchor:[40,18]})});
}
function mkDxC(lat,lng,color,name) {
  return L.marker([lat,lng],{icon:L.divIcon({className:'',html:'<div style="font-weight:700;font-size:11px;color:'+color+';text-shadow:0 0 4px #fff,0 0 8px #fff;">'+name+'</div>',iconSize:null,iconAnchor:[20,8]})});
}
function mkLead(fLat,fLng,tLat,tLng,color) {
  return L.polyline([[fLat,fLng],[tLat,tLng]],{color:color,weight:1.5,opacity:0.3,dashArray:'4,4'});
}

// ── fitBounds ──
var ab = L.latLngBounds(cityPosData[0]?[cityPosData[0].lat,cityPosData[0].lng]:[0,0]);
function extA(arr){for(var i=0;i<arr.length;i++)ab.extend(arr[i]);}
for(var i=0;i<mainRoutes.length;i++) extA(mainRoutes[i][1]);
for(var i=0;i<spurRoutes.length;i++) extA(spurRoutes[i][1]);
cityPosData.forEach(function(c){ab.extend([c.lat,c.lng]);});
dxData.forEach(function(d){ab.extend([d.lat,d.lng]);});
majorSpots.forEach(function(s){ab.extend([s[0],s[1]]);});
spots.forEach(function(s){ab.extend([s[0],s[1]]);});
map.fitBounds(ab,{padding:[50,50]});
var overviewBounds = map.getBounds();
var focusCfg = {{FOCUS_JSON}};
var poiZoom = {{POI_ZOOM_JSON}};
var focusActive = false;
var focusBtn = document.getElementById('focus-btn');
if (focusCfg && focusCfg.center && focusCfg.zoom) {
  focusBtn.style.display = 'block';
  focusBtn.textContent = focusCfg.label || '聚焦路线';
  focusBtn.addEventListener('click', function() {
    focusActive = !focusActive;
    focusBtn.setAttribute('aria-pressed', focusActive ? 'true' : 'false');
    if (focusActive) {
      focusBtn.textContent = '查看全程';
      map.flyTo(focusCfg.center, focusCfg.zoom, {duration: 0.8});
    } else {
      focusBtn.textContent = focusCfg.label || '聚焦路线';
      map.fitBounds(overviewBounds, {padding: [50, 50]});
    }
  });
}

// ── Zoom 处理器 ──
function u() {
  var z = map.getZoom();
  document.getElementById('zoom-display').textContent = 'Zoom ' + z;
  
  var cfg = CFG[0];
  for (var ci=0;ci<CFG.length;ci++)
    if (z>=CFG[ci].zMin&&z<=CFG[ci].zMax) {cfg=CFG[ci];break;}
  
  // 路线线段 → 像素
  var segPx = [];
  for (var i=0;i<routeSegData.length;i++) {
    var p1 = map.latLngToLayerPoint(L.latLng(routeSegData[i][0][0],routeSegData[i][0][1]));
    var p2 = map.latLngToLayerPoint(L.latLng(routeSegData[i][1][0],routeSegData[i][1][1]));
    segPx.push({x1:p1.x,y1:p1.y,x2:p2.x,y2:p2.y});
  }
  // 圆点 → 像素
  var dp = [];
  for (var i=0;i<cityPosData.length;i++) {
    var p = map.latLngToLayerPoint(L.latLng(cityPosData[i].lat,cityPosData[i].lng));
    dp.push(p);
  }
  
  labelLayer.clearLayers();
  leadLayer.clearLayers();
  
  var boxes = [];
  for (var i=0;i<cityPosData.length;i++) {
    var c = cityPosData[i];
    var cw = mw(c.name,14)+12;
    var p = findPos(c.lat,c.lng,cfg.basePx,cw,20,segPx,dp,boxes,true);
    boxes.push(p.box);
    labelLayer.addLayer(mkCity(p.lat,p.lng,c.color,c.name));
    if (cfg.lead) leadLayer.addLayer(mkLead(c.lat,c.lng,p.lat,p.lng,c.color));
  }
  
  for (var i=0;i<dxData.length;i++) {
    var d = dxData[i];
    if (cfg.compact) {
      var nameW = mw(d.name, 12);
      var distText = d.sub || (d.dist ? d.dist.replace('🚗 ','') : '');
      var distW = distText ? mw(distText, 10) : 0;
      var labelW = Math.max(nameW, distW) + 12;
      var labelH = distText ? 30 : 16;
      var p = findPos(d.lat,d.lng,cfg.basePx*0.7,labelW,labelH,segPx,dp,boxes,true);
      boxes.push(p.box);
      var lbl = '<div style="text-align:center;line-height:1.3;"><div style="font-weight:700;font-size:12px;color:'+d.color+';text-shadow:0 0 4px #fff,0 0 8px #fff;">'+d.name+'</div>';
      if (distText) lbl += '<div style="font-size:10px;color:'+d.color+';text-shadow:0 0 4px #fff,0 0 8px #fff;">'+distText+'</div>';
      lbl += '</div>';
      labelLayer.addLayer(L.marker([p.lat,p.lng],{icon:L.divIcon({className:'',html:lbl,iconSize:[labelW,labelH],iconAnchor:[Math.round(labelW/2),Math.round(labelH/2)]})}));
    } else {
      var p = findPos(d.lat,d.lng,cfg.basePx*0.7,80,36,segPx,dp,boxes,false);
      boxes.push(p.box);
      labelLayer.addLayer(mkDx(p.lat,p.lng,d.color,d.name,d.sub||'',d.dist||''));
    }
  }
  
  // POI
  spurLayer.clearLayers();
  if (z>=10) {
    for (var i=0;i<spurRoutes.length;i++)
      spurLayer.addLayer(L.polyline(spurRoutes[i][1],{
        color: spurRoutes[i][0],
        weight: 3,
        opacity: spurRoutes[i][2] === 'estimated' ? 0.5 : 0.6,
        dashArray: spurRoutes[i][2] === 'estimated' ? '7,5' : null,
        smoothFactor: 1
      }));
  }
  var compactAdjust = map.getSize().x < 420 ? 1 : 0;
  var majorMinZoom = poiZoom.major + compactAdjust;
  var minorMinZoom = poiZoom.minor + compactAdjust;
  if (z>=majorMinZoom&&!map.hasLayer(poiMajor)) map.addLayer(poiMajor);
  else if (z<majorMinZoom&&map.hasLayer(poiMajor)) map.removeLayer(poiMajor);
  if (z>=minorMinZoom&&!map.hasLayer(poiMinor)) map.addLayer(poiMinor);
  else if (z<minorMinZoom&&map.hasLayer(poiMinor)) map.removeLayer(poiMinor);
  if (!map.hasLayer(spurLayer)) map.addLayer(spurLayer);
  
  if (map.hasLayer(dotLayer)){map.removeLayer(dotLayer);map.addLayer(dotLayer);}
  if (map.hasLayer(labelLayer)){map.removeLayer(labelLayer);map.addLayer(labelLayer);}
}
map.on('zoomend',u); u();

// ── 全屏切换 ──
function toggleMapFullscreen() {
  var el = document.getElementById('map-section');
  el.classList.toggle('fullscreen');
  var btn = document.getElementById('fullscreen-btn');
  btn.textContent = el.classList.contains('fullscreen') ? '✕' : '⛶';
  btn.title = el.classList.contains('fullscreen') ? '退出全屏' : '全屏浏览';
  btn.setAttribute('aria-label', btn.title);
  // 延迟让 CSS transition 完成后刷新地图
  setTimeout(function(){ map.invalidateSize(); }, 350);
}
document.getElementById('fullscreen-btn').addEventListener('click', toggleMapFullscreen);

// ── 微观日志展开／收起 ──
document.querySelectorAll('.timeline-toggle').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var panel = document.getElementById(this.getAttribute('aria-controls'));
    var expanded = this.getAttribute('aria-expanded') === 'true';
    this.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    this.querySelector('.timeline-chevron').textContent = expanded ? '▼' : '▶';
    panel.hidden = expanded;
  });
});

// ESC 退出全屏
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    var el = document.getElementById('map-section');
    if (el.classList.contains('fullscreen')) {
      el.classList.remove('fullscreen');
      var btn = document.getElementById('fullscreen-btn');
      btn.textContent = '⛶';
      btn.title = '全屏浏览';
      btn.setAttribute('aria-label', '全屏浏览地图');
      setTimeout(function(){ map.invalidateSize(); }, 350);
    }
  }
});
