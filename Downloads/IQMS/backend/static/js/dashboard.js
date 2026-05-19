/**
 * AQIMS — Dashboard JS v2
 * WebSocket temps réel + ECharts + Recommandations
 */

const AQI_LEVELS = [
  { min:0,   max:50,  label:'Bon',          color:'#22c55e' },
  { min:51,  max:100, label:'Modéré',        color:'#f59e0b' },
  { min:101, max:150, label:'Mauvais',       color:'#f97316' },
  { min:151, max:200, label:'Très mauvais',  color:'#ef4444' },
  { min:201, max:300, label:'Dangereux',     color:'#8b5cf6' },
  { min:301, max:500, label:'Extrême',       color:'#7e0023' },
];

function getAqiInfo(aqi) {
  return AQI_LEVELS.find(l => aqi >= l.min && aqi <= l.max) || { label:'Inconnu', color:'#9ca3af' };
}

function chartColors(dark) {
  return dark
    ? { axis:'#6b7280', grid:'#1f2937', line:'#374151', bg:'transparent' }
    : { axis:'#9ca3af', grid:'#f9fafb', line:'#e5e7eb', bg:'transparent' };
}

const MAX_POINTS = 30;
const timeLabels=[], aqiData=[], coData=[], ldrData=[], tempData=[], humData=[];

function dashboard() {
  return {
    devices:[], avgAqi:0, avgCo:0,
    aqiColor:'#9ca3af', aqiLabel:'En attente...',
    onlineDevices:0, activeAlerts:0,
    recommendations:[],
    gaugeChart:null, aqiChart:null, coChart:null, ldrChart:null, thChart:null,
    ws:null, wsConnected:false, reconnectDelay:2000,

    // Étapes du cycle (style BrainBox AI)
    cycle: ['Collecter','Calculer','Rapport','Comparer','Implémenter',
            'Suivre','Identifier','Réduire','Mesurer','Améliorer'],

    init() {
      this.$nextTick(() => {
        this.initCharts();
        this.connectWebSocket();
        this.loadInitialData();
        this.loadRecommendations();
        lucide.createIcons();
      });
      window.addEventListener('theme-change', (e) => this._applyChartTheme(e.detail.dark));
      // Rafraîchir les recommandations toutes les 30s
      setInterval(() => this.loadRecommendations(), 30000);
    },

    async loadInitialData() {
      try {
        const res = await fetch('/api/v1/dashboard/latest');
        if (!res.ok) return;
        const json = await res.json();
        json.data.forEach(d => this.processReading(d));
        this.updateKPIs(); this.updateCharts();
      } catch(e) { console.warn('Données initiales indisponibles', e); }
      // Charger le nombre d'alertes actives
      try {
        const sr = await fetch('/api/v1/dashboard/summary');
        if (sr.ok) {
          const sj = await sr.json();
          if (sj.active_alerts != null) this.activeAlerts = sj.active_alerts;
        }
      } catch(e) {}
    },

    async loadRecommendations() {
      try {
        const res = await fetch('/api/v1/dashboard/recommendations');
        if (!res.ok) return;
        const json = await res.json();
        this.recommendations = json.recommendations || [];
        this.$nextTick(() => lucide.createIcons());
      } catch(e) {}
    },

    connectWebSocket() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.ws = new WebSocket(`${proto}//${location.host}/ws`);
      this.ws.onopen = () => {
        this.wsConnected = true; this.reconnectDelay = 2000; this.setWsStatus(true);
      };
      this.ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'sensor_data') {
            this.processReading(msg.data);
            this.updateKPIs(); this.updateCharts();
          }
        } catch(e) {}
      };
      this.ws.onclose = () => {
        this.wsConnected = false; this.setWsStatus(false);
        setTimeout(() => {
          this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
          this.connectWebSocket();
        }, this.reconnectDelay);
      };
    },

    setWsStatus(ok) {
      const dot = document.getElementById('ws-dot');
      const txt = document.getElementById('ws-text');
      if (!dot || !txt) return;
      dot.className = ok
        ? 'w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse'
        : 'w-1.5 h-1.5 rounded-full bg-red-400';
      txt.textContent = ok ? 'Temps réel' : 'Déconnecté';
      txt.className   = ok ? 'text-emerald-500' : 'text-red-500';
    },

    processReading(data) {
      const id  = data.device_id;
      const idx = this.devices.findIndex(d => d.device_id === id);
      const dev = {
        device_id:   id,
        name:        data.name || id,
        location:    data.location || '—',
        is_online:   true,
        aqi:         data.aqi,
        co_ppm:      data.co_ppm,
        lux:         data.lux,
        temperature: data.temperature,
        humidity:    data.humidity,
      };
      if (idx >= 0) this.devices[idx] = dev; else this.devices.push(dev);

      const t = new Date(data.timestamp || Date.now()).toLocaleTimeString('fr-CA');
      this._push(timeLabels, t);
      this._push(aqiData,    data.aqi);
      this._push(coData,     data.co_ppm);
      this._push(ldrData,    data.lux);
      this._push(tempData,   data.temperature);
      this._push(humData,    data.humidity);
    },

    _push(arr, v) { arr.push(v); if (arr.length > MAX_POINTS) arr.shift(); },

    updateKPIs() {
      const online = this.devices.filter(d => d.is_online);
      this.onlineDevices = online.length;
      if (!online.length) return;

      const aqis = online.map(d => d.aqi).filter(v => v != null);
      this.avgAqi = aqis.length
        ? Math.round(aqis.reduce((a, b) => a + b, 0) / aqis.length) : 0;

      const cos = online.map(d => d.co_ppm).filter(v => v != null);
      this.avgCo = cos.length
        ? (cos.reduce((a, b) => a + b, 0) / cos.length).toFixed(1) : 0;

      const info = getAqiInfo(this.avgAqi);
      this.aqiColor = info.color;
      this.aqiLabel = info.label;

      if (this.gaugeChart) {
        this.gaugeChart.setOption({
          series:[{ data:[{ value: this.avgAqi, name: info.label }] }]
        });
      }
    },

    updateCharts() {
      const xl = [...timeLabels];
      if (this.aqiChart)  this.aqiChart.setOption({ series:[{ data:[...aqiData] }], xAxis:[{ data: xl }] });
      if (this.coChart)   this.coChart.setOption({  series:[{ data:[...coData] }],  xAxis:[{ data: xl }] });
      if (this.ldrChart)  this.ldrChart.setOption({ series:[{ data: ldrData.map(v => v ? Math.round(v) : null) }], xAxis:[{ data: xl }] });
      if (this.thChart)   this.thChart.setOption({
        series:[
          { data: tempData.map(v => v?.toFixed(1) ?? null) },
          { data: humData.map(v =>  v?.toFixed(1) ?? null) },
        ],
        xAxis:[{ data: xl }]
      });
    },

    _applyChartTheme(dark) {
      const c = chartColors(dark);
      const axisOpts = {
        xAxis:[{ axisLabel:{color:c.axis}, axisLine:{lineStyle:{color:c.line}} }],
        yAxis:[{ axisLabel:{color:c.axis}, splitLine:{lineStyle:{color:c.grid}} }],
        backgroundColor: c.bg,
      };
      [this.aqiChart, this.coChart, this.ldrChart].forEach(ch => ch?.setOption(axisOpts));
      this.thChart?.setOption({...axisOpts, legend:{ textStyle:{color:c.axis} }});
      this.gaugeChart?.setOption({
        series:[{ axisLabel:{color:c.axis}, title:{color: dark ? '#9ca3af':'#6b7280'} }]
      });
    },

    initCharts() {
      const dark = document.documentElement.classList.contains('dark');
      this._initGauge(dark);
      this._initAqiChart(dark);
      this._initCoChart(dark);
      this._initLdrChart(dark);
      this._initThChart(dark);
      window.addEventListener('resize', () =>
        [this.gaugeChart, this.aqiChart, this.coChart, this.ldrChart, this.thChart]
          .forEach(c => c?.resize())
      );
    },

    _initGauge(dark) {
      const el = document.getElementById('aqi-gauge'); if (!el) return;
      const c = chartColors(dark);
      this.gaugeChart = echarts.init(el);
      this.gaugeChart.setOption({
        backgroundColor: 'transparent',
        series:[{
          type:'gauge', startAngle:210, endAngle:-30, min:0, max:300, radius:'88%',
          pointer:{ length:'65%', width:4, itemStyle:{color:'auto'} },
          progress:{ show:true, width:10 },
          axisLine:{ lineStyle:{ width:10, color:[
            [50/300,'#22c55e'],[100/300,'#f59e0b'],[150/300,'#f97316'],
            [200/300,'#ef4444'],[300/300,'#8b5cf6']
          ]}},
          axisTick:{show:false}, splitLine:{show:false},
          axisLabel:{ distance:16, color:c.axis, fontSize:10,
            formatter: v => [0,50,100,150,200,300].includes(v) ? v : '' },
          detail:{ valueAnimation:true, fontSize:28, fontWeight:'bold',
                   offsetCenter:[0,'65%'], color:'auto' },
          title:{ offsetCenter:[0,'90%'], fontSize:12, color: dark?'#9ca3af':'#6b7280' },
          data:[{value:0, name:'En attente...'}],
        }],
      });
    },

    _initAqiChart(dark) {
      const el = document.getElementById('aqi-chart'); if (!el) return;
      this.aqiChart = echarts.init(el);
      this.aqiChart.setOption(this._lineOpts({
        name:'AQI', color:'#10b981', dark,
        markLines:[
          {yAxis:50,  lineStyle:{color:'#22c55e',  type:'dashed', opacity:.5}},
          {yAxis:100, lineStyle:{color:'#f59e0b',  type:'dashed', opacity:.5}},
          {yAxis:150, lineStyle:{color:'#f97316',  type:'dashed', opacity:.5}},
        ]
      }));
    },

    _initCoChart(dark) {
      const el = document.getElementById('co-chart'); if (!el) return;
      this.coChart = echarts.init(el);
      this.coChart.setOption(this._lineOpts({
        name:'CO (ppm)', color:'#f97316', dark,
        markLines:[{yAxis:9, lineStyle:{color:'#ef4444', type:'dashed', opacity:.6}}]
      }));
    },

    _initLdrChart(dark) {
      const el = document.getElementById('ldr-chart'); if (!el) return;
      this.ldrChart = echarts.init(el);
      this.ldrChart.setOption(this._lineOpts({name:'Lux', color:'#f59e0b', dark}));
    },

    _initThChart(dark) {
      const el = document.getElementById('th-chart'); if (!el) return;
      const c = chartColors(dark);
      this.thChart = echarts.init(el);
      this.thChart.setOption({
        backgroundColor:'transparent',
        tooltip:{trigger:'axis'},
        legend:{ data:['Temp. (°C)','Humidité (%)'], top:0, right:0,
                 textStyle:{color:c.axis, fontSize:10}, itemWidth:12, itemHeight:3 },
        grid:{left:38, right:10, top:28, bottom:28},
        xAxis:{type:'category', data:timeLabels,
               axisLabel:{color:c.axis, fontSize:9}, axisLine:{lineStyle:{color:c.line}}},
        yAxis:{type:'value', axisLabel:{color:c.axis, fontSize:10},
               splitLine:{lineStyle:{color:c.grid}}},
        series:[
          { name:'Temp. (°C)',   type:'line', data:tempData, smooth:true, symbol:'none',
            lineStyle:{color:'#ef4444', width:2} },
          { name:'Humidité (%)', type:'line', data:humData,  smooth:true, symbol:'none',
            lineStyle:{color:'#3b82f6', width:2} },
        ],
      });
    },

    _lineOpts({name, color, dark, markLines=[]}) {
      const c = chartColors(dark);
      return {
        backgroundColor: 'transparent',
        tooltip:{trigger:'axis'},
        grid:{left:38, right:10, top:8, bottom:28},
        xAxis:{type:'category', data:timeLabels,
               axisLabel:{color:c.axis, fontSize:9}, axisLine:{lineStyle:{color:c.line}}},
        yAxis:{type:'value', axisLabel:{color:c.axis, fontSize:10},
               splitLine:{lineStyle:{color:c.grid}}},
        series:[{
          name, type:'line', data:[], smooth:true, symbol:'none',
          lineStyle:{color, width:2},
          areaStyle:{color:{type:'linear', x:0, y:0, x2:0, y2:1,
            colorStops:[{offset:0,color:color+'28'},{offset:1,color:color+'04'}]}},
          markLine: markLines.length ? {
            silent:true, symbol:'none',
            data: markLines.map(l => [{yAxis:l.yAxis},{yAxis:l.yAxis}]),
            lineStyle: markLines[0]?.lineStyle || {},
          } : undefined,
        }],
      };
    },

    getAqiColor(aqi) { return getAqiInfo(aqi ?? 0).color; },
  };
}
