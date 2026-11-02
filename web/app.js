/* 会议纪要 App v3.0 —— 纯前端逻辑
 * 新增：本地离线 ASR 引擎（openai-whisper）、引擎选择、模型状态显示
 * 语音转写优先级：本地引擎 > 在线 ASR > 浏览器 Web Speech API */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const els = {
    status: $('status'),
    btnRecord: $('btnRecord'),
    timer: $('timer'),
    hint: $('hint'),
    liveText: $('liveText'),
    transcript: $('transcript'),
    wordCount: $('wordCount'),
    btnCorrect: $('btnCorrect'),
    result: $('result'),
    btnSummarize: $('btnSummarize'),
    engineTag: $('engineTag'),
    btnCopy: $('btnCopy'),
    btnExport: $('btnExport'),
    toast: $('toast'),
  };

  const state = {
    mode: 'live',
    engine: 'auto',
    asrEngine: 'auto',  // 'auto' | 'local' | 'online' | 'browser'
    recording: false,
    seconds: 0,
    timerId: null,
    recognition: null,
    recorder: null,
    chunks: [],
    mime: '',
    restartTimer: null,
    interimHistory: '',
    cap: { live: false, asr: false, llm: false, localAsr: false, localModelLoaded: false },
    doc: null,
    meta: { topic: '', members: '' },
  };

  const STORE_DOCS = 'meeting_notes_v3';
  const STORE_META = 'meeting_meta_v3';

  const SAMPLE = [
    '好，人到齐了，我们开始今天的周会。先说上个月 AI 赋能体系的进展。',
    '张磊：需求工程那边已经把术语本体库的第一版整理出来了，大概三百多个条目，覆盖了核心业务词。',
    '李娜：但问题和代码库的映射还没打通，我们现在只能人工对照，效率比较低。',
    '张磊：这块我下周会跟平台组对接，争取月底前把接口跑通。',
    '王总：我补充一点，这个方向是对的，但不要太追求大而全，先把研发中心最痛的两个场景做透。',
    '李娜：同意，我建议优先做需求评审和测试用例生成这两个场景，投入产出比最高。',
    '王总：那就定了，第一阶段只做这两个场景，其他需求先放一放。',
    '张磊：风险是现在缺一个稳定的评测集，没有评测集我们没法证明效果提升了多少。',
    '王总：评测的事情李娜牵头，两周内出一个最小版本的评测集，至少覆盖五十条样本。',
    '李娜：可以，我这边本周内先拉一个初稿出来，下周三之前给到大家评审。',
    '张磊：另外提醒一下，如果月底接口还没通，第一阶段的验收时间可能要往后推。',
    '王总：那就这样，散会。'
  ].join('\n');

  /* ---------------- 工具 ---------------- */
  let toastTimer = null;
  function toast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove('show'), 2200);
  }

  function setStatus(text, cls) {
    els.status.textContent = text;
    els.status.className = 'status ' + (cls || 'status-idle');
  }

  function fmtTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const pad = (n) => String(n).padStart(2, '0');
    return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function nowLabel() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  /* ---------------- 文本规范化 ---------------- */
  const CN_PUNCT = {
    ',': '，', '.': '。', ';': '；', ':': '：',
    '?': '？', '!': '！', '(': '（', ')': '）',
  };

  const ASR_HOMOPHONE_FIX = {
    '求工程': '需求工程', '须求工程': '需求工程',
    '属于本体库': '术语本体库', '术语本提库': '术语本体库',
    '撤试用例': '测试用例', '测试用里': '测试用例', '测试用力': '测试用例', '侧试用例': '测试用例',
    '大儿全': '大而全', '大二全': '大而全',
    '平局级': '评测集', '评车机': '评测集',
    '代码裤': '代码库', '需且': '需求', '板本': '版本', '部属': '部署',
    '几口': '接口', '原形': '原型',
  };

  function normalizeText(text) {
    let t = text;
    const sortedKeys = Object.keys(ASR_HOMOPHONE_FIX).sort((a, b) => b.length - a.length);
    for (const wrong of sortedKeys) {
      t = t.split(wrong).join(ASR_HOMOPHONE_FIX[wrong]);
    }
    for (const [k, v] of Object.entries(CN_PUNCT)) {
      t = t.replace(new RegExp('\\' + k, 'g'), v);
    }
    t = t.replace(/[嗯啊哦呃诶哎嘛呐哈嘿哟]{1,4}/g, '');
    t = t.replace(/(那个|就是说|然后呢|所以呢|这个呢|对吧|是吧|好的|明白了|就那个|你知道吧)/g, '');
    t = t.replace(/[ 　\t]+/g, '');
    t = t.replace(/\n{3,}/g, '\n\n');
    if (t && !/[。！？!?\n]$/.test(t)) t += '。';
    return t.trim();
  }

  function appendText(text) {
    if (!text) return;
    const cleaned = normalizeText(text);
    if (!cleaned) return;
    const el = els.transcript;
    const needsBreak = el.value && !/[\n。！？!?；;]$/.test(el.value.trim());
    el.value += (needsBreak ? '\n' : '') + cleaned;
    el.scrollTop = el.scrollHeight;
    updateCount();
  }

  function updateCount() {
    const n = els.transcript.value.replace(/\s/g, '').length;
    els.wordCount.textContent = n + ' 字';
  }

  /* ---------------- 实时语音识别（浏览器 Web Speech API） ---------------- */
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  function startLive() {
    if (!SR) {
      toast('当前浏览器不支持实时识别，请改用「录音转写」');
      return;
    }
    const MAX_SILENCE_RESTARTS = 12;
    const MAX_ERROR_RETRIES = 2;
    let silenceRestarts = 0;
    let errorRetries = 0;
    let stopping = false;

    function tryStopAndCleanup(reason) {
      if (stopping) return;
      stopping = true;
      if (state.interimHistory && state.interimHistory.trim()) {
        appendText(state.interimHistory.trim());
        state.interimHistory = '';
      }
      state.recognition = null;
      clearTimeout(state.restartTimer);
      els.liveText.textContent = '已停止';
      stopRecording(true);
      if (reason) toast(reason);
    }

    const rec = new SR();
    rec.lang = 'zh-CN';
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      state.recording = true;
      state.interimHistory = '';
      setStatus('识别中 (浏览器)', 'status-rec');
      els.btnRecord.classList.add('recording');
      els.btnRecord.querySelector('.record-label').textContent = '停止记录';
      els.hint.textContent = '正在听…说话内容会自动变成文字';
      startTimer();
    };

    rec.onresult = (event) => {
      silenceRestarts = 0;
      errorRetries = 0;
      let interim = '';
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const item = event.results[i];
        if (item.isFinal) finalText += item[0].transcript;
        else interim += item[0].transcript;
      }
      if (finalText) {
        appendText(finalText.trim());
        state.interimHistory = '';
      }
      if (interim) {
        state.interimHistory = interim;
        els.liveText.textContent = interim;
      } else if (finalText) {
        els.liveText.textContent = '…';
      }
    };

    rec.onerror = (event) => {
      if (event.error === 'no-speech') {
        silenceRestarts += 1;
        if (silenceRestarts > MAX_SILENCE_RESTARTS) {
          tryStopAndCleanup('长时间未检测到语音，已自动停止');
        }
        return;
      }
      if (event.error === 'aborted') return;
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        tryStopAndCleanup('麦克风权限被拒绝，请在浏览器设置中允许后再试');
        return;
      }
      if (event.error === 'network') {
        errorRetries += 1;
        if (errorRetries > MAX_ERROR_RETRIES) {
          tryStopAndCleanup('浏览器语音识别不可达（需 Google 服务器），请改用「录音转写」模式。');
        }
        return;
      }
      tryStopAndCleanup('语音识别出错（' + event.error + '），请改用「录音转写」模式。');
    };

    rec.onend = () => {
      if (stopping || !state.recording) return;
      if (state.interimHistory && state.interimHistory.trim()) {
        appendText(state.interimHistory.trim());
        state.interimHistory = '';
      }
      if (silenceRestarts > MAX_SILENCE_RESTARTS || errorRetries > MAX_ERROR_RETRIES) {
        tryStopAndCleanup();
        return;
      }
      clearTimeout(state.restartTimer);
      state.restartTimer = setTimeout(() => {
        if (stopping || !state.recording) return;
        try { rec.start(); } catch (e) {
          tryStopAndCleanup('语音识别已断开，请重新点击「开始记录」');
        }
      }, 250);
    };

    state.recognition = rec;
    try {
      rec.start();
    } catch (e) {
      tryStopAndCleanup('启动语音识别失败：' + e.message);
    }
  }

  function stopLive() {
    if (state.interimHistory && state.interimHistory.trim()) {
      appendText(state.interimHistory.trim());
      state.interimHistory = '';
    }
    if (state.recognition) {
      try { state.recognition.stop(); } catch (e) { /* ignore */ }
      state.recognition = null;
    }
    els.liveText.textContent = '已停止';
  }

  /* ---------------- 录音上传转写（服务端 ASR） ---------------- */
  function pickMime() {
    if (typeof MediaRecorder === 'undefined') return '';
    const list = ['audio/webm;codecs=opus', 'audio/webm', 'audio/webm;codecs=pcm', 'audio/mp4'];
    return list.find((t) => MediaRecorder.isTypeSupported(t)) || '';
  }

  function bestAudioConstraints() {
    return {
      audio: {
        channelCount: { ideal: 1 },
        sampleRate: { ideal: 48000, min: 16000 },
        echoCancellation: { ideal: true },
        noiseSuppression: { ideal: true },
        autoGainControl: { ideal: true },
      },
    };
  }

  function getAsrEngineLabel() {
    if (state.asrEngine === 'local') return '本地';
    if (state.asrEngine === 'online') return '在线';
    if (state.cap.localAsr) return '本地';
    if (state.cap.asr) return '在线';
    return '浏览器';
  }

  async function startUploadMode() {
    const hasAnyAsr = state.cap.localAsr || state.cap.asr;
    if (!hasAnyAsr) {
      toast('未配置语音转写引擎。请安装 faster-whisper（pip install faster-whisper）或在 .env 配置 ASR_API_KEY');
      openSettings();
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast('当前环境不支持录音，请直接用文字输入');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(bestAudioConstraints());
    } catch (e) {
      toast('无法获取麦克风：' + e.message);
      return;
    }
    const track = stream.getAudioTracks()[0];
    if (track) {
      const settings = track.getSettings();
      console.log('[录音] 采样率:', settings.sampleRate, '声道:', settings.channelCount);
    }
    state.mime = pickMime();
    const recorderOpts = { audioBitsPerSecond: 128000 };
    if (state.mime) recorderOpts.mimeType = state.mime;
    let recorder;
    try {
      recorder = new MediaRecorder(stream, recorderOpts);
    } catch (e) {
      toast('录音初始化失败：' + e.message);
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    state.chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) state.chunks.push(e.data);
    };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(state.chunks, { type: state.mime || 'audio/webm' });
      state.chunks = [];
      if (blob.size < 1000) {
        toast('录音时间太短');
        return;
      }
      await uploadAudio(blob);
    };
    state.recorder = recorder;
    recorder.start(1000);
    state.recording = true;
    const engineLabel = getAsrEngineLabel();
    setStatus('录音中', 'status-rec');
    els.btnRecord.classList.add('recording');
    els.btnRecord.querySelector('.record-label').textContent = '停止并转写';
    els.hint.textContent = `录音中 (${engineLabel}引擎)，停止后自动转写`;
    startTimer();
  }

  function stopUploadMode() {
    if (state.recorder && state.recorder.state !== 'inactive') {
      state.recorder.stop();
    }
    state.recorder = null;
  }

  async function uploadAudio(blob) {
    const engineLabel = getAsrEngineLabel();
    setStatus(`转写中 (${engineLabel})`, 'status-run');
    // 首次使用本地引擎时先触发预加载
    if (state.asrEngine === 'local' || (state.asrEngine === 'auto' && state.cap.localAsr)) {
      try {
        await fetch('/api/model/preload', { method: 'GET' });
      } catch (e) { /* preload is best-effort */ }
    }
    els.hint.textContent = '正在转写…（首次使用本地引擎需下载模型，约 1-2 分钟）';
    const t = blob.type;
    let ext = 'wav';
    if (t.includes('webm')) ext = 'webm';
    else if (t.includes('mp4')) ext = 'm4a';
    else if (t.includes('ogg')) ext = 'ogg';
    const form = new FormData();
    form.append('file', blob, `meeting.${ext}`);
    form.append('engine', state.asrEngine);

    try {
      const resp = await fetch('/api/asr', { method: 'POST', body: form });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
      const text = (data.text || '').trim();
      if (!text) {
        toast('没有识别到内容，请重试');
      } else {
        appendText(text);
        const provider = data.provider || '?';
        toast(`转写完成 (${provider})`);
      }
      els.hint.textContent = `转写完成 (${engineLabel})，可点「文字纠错」提升准确率`;
    } catch (e) {
      toast('转写失败：' + e.message);
      els.hint.textContent = '转写失败，可重试';
    } finally {
      setStatus('待命', 'status-idle');
    }
  }

  /* ---------------- 文字纠错 ---------------- */
  async function correctText() {
    const text = els.transcript.value.trim();
    if (!text) { toast('没有可纠错的文字'); return; }
    els.btnCorrect.disabled = true;
    setStatus('纠错中', 'status-run');
    if (state.cap.llm) {
      try {
        const resp = await fetch('/api/correct', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        });
        const data = await resp.json().catch(() => ({}));
        if (resp.ok && data.text && data.text !== text) {
          els.transcript.value = data.text;
          updateCount();
          toast(data.corrected ? '文字已LLM纠错优化' : '文字已规范化');
          setStatus('待命', 'status-idle');
          els.btnCorrect.disabled = false;
          return;
        }
      } catch (e) { /* fall through */ }
    }
    const normalized = normalizeText(text);
    if (normalized !== text) {
      els.transcript.value = normalized;
      updateCount();
      toast('文字已本地规范化');
    } else {
      toast('文字已是最优状态');
    }
    setStatus('待命', 'status-idle');
    els.btnCorrect.disabled = false;
  }

  /* ---------------- 计时与开关 ---------------- */
  function startTimer() {
    state.seconds = 0;
    els.timer.textContent = '00:00';
    clearInterval(state.timerId);
    state.timerId = setInterval(() => {
      state.seconds += 1;
      els.timer.textContent = fmtTime(state.seconds);
    }, 1000);
  }

  function stopTimer() {
    clearInterval(state.timerId);
    state.timerId = null;
  }

  function startRecording() {
    if (state.mode === 'live') startLive();
    else startUploadMode();
  }

  function stopRecording(silent) {
    state.recording = false;
    state.interimHistory = '';
    clearTimeout(state.restartTimer);
    if (state.mode === 'live') stopLive();
    else stopUploadMode();
    stopTimer();
    els.btnRecord.classList.remove('recording');
    els.btnRecord.querySelector('.record-label').textContent = '开始记录';
    els.hint.textContent = silent ? '已停止' : '已停止，可以生成纪要了';
    if (!silent) setStatus('待命', 'status-idle');
  }

  /* ---------------- 本地规则引擎 (与 v2 一致) ---------------- */
  const BUSINESS_WHITELIST = new Set([
    '需求工程', '需求分析', '需求评审', '本体库', '术语库', '知识图谱', '代码库', '代码仓库',
    '测试用例', '测试集', '评测集', '接口对接', 'API', '接口文档', '产品经理', '项目经理',
    '技术负责人', '架构师', '进度跟踪', '里程碑', '交付日期', '系统架构', '技术方案',
    '技术选型', '上线部署', '性能优化', '代码审查', '单元测试', '集成测试', '回归测试',
    '用户体验', '交互设计', '自动化测试', '持续集成', '持续部署', 'CI/CD', '工作流',
    '流程优化', 'Bug修复', '缺陷管理', '算法模型', '机器学习', '深度学习', '大模型', 'AI赋能',
    '运维监控', '版本管理', '文档编写', '技术分享',
  ]);

  const PRECISE_STOP = new Set([
    '的了', '是在', '就是', '还是', '已经', '自己', '以及', '对于', '通过', '进行', '还有', '可能',
    '应该', '知道', '觉得', '目前', '现在', '可以', '我们', '你们', '他们', '她们', '大家',
    '一下', '一个', '什么', '没有', '如果', '因为', '所以', '但是', '然后', '不过', '只是',
    '关于', '来说', '这个', '那个', '这些', '那些', '其中', '其实', '主要', '非常', '特别',
    '真的', '比较', '更加', '所有', '很多', '一些', '一点', '是否', '能否', '不同', '一样',
    '各自', '另外', '之前', '之后', '以后', '以前', '当时', '而已', '需要', '建议',
  ]);

  const HARD_BLACK_CHARS = '的了着吗呢吧啊嗯哦呀嘛哈嘿哟嘘吧哪嘎铛咚噢';

  function isGoodWord(word) {
    if (word.length < 2 || word.length > 6) return false;
    if (!/^[\u4e00-\u9fa5]{2,6}$/.test(word)) return false;
    if (BUSINESS_WHITELIST.has(word)) return true;
    for (const ch of word) { if (HARD_BLACK_CHARS.includes(ch)) return false; }
    if (PRECISE_STOP.has(word)) return false;
    if ([...word].every((c) => '的了一是不在有人我这那都也很会和要就'.includes(c))) return false;
    if (/\d/.test(word)) return false;
    return true;
  }

  function splitSentences(text) {
    const rawParts = text.replace(/\r/g, '').split(/(?<=[。！？!?；;；\n])/);
    const result = [];
    for (const part of rawParts) {
      const trimmed = part.trim();
      if (!trimmed || trimmed.length < 4) continue;
      if (trimmed.length > 80 && !/[。！？!?；;]/.test(trimmed)) {
        for (const sub of splitLongNoPunct(trimmed)) {
          if (sub.length >= 4) result.push(sub);
        }
      } else {
        result.push(trimmed);
      }
    }
    return result;
  }

  const CLAUSE_MARKERS = /(然后|但是|不过|所以|因为|如果|另外|此外|还有|总之|关键|特别|尤其|首先|其次|最后|接下来|同时|而且|并且)/g;

  function splitLongNoPunct(text) {
    const clauses = [];
    let lastIdx = 0;
    let match;
    CLAUSE_MARKERS.lastIndex = 0;
    while ((match = CLAUSE_MARKERS.exec(text)) !== null) {
      const before = text.slice(lastIdx, match.index).trim();
      if (before.length >= 4) clauses.push(before);
      lastIdx = match.index;
    }
    const tail = text.slice(lastIdx).trim();
    if (tail.length >= 4) clauses.push(tail);
    return clauses.length ? clauses : [text];
  }

  function extractKeywords(sentences, topN) {
    const counts = new Map();
    for (const s of sentences) {
      for (const term of BUSINESS_WHITELIST) {
        if (s.includes(term)) counts.set(term, (counts.get(term) || 0) + 1);
      }
      const chunks = s.match(/[\u4e00-\u9fa5]{2,}/g) || [];
      for (const chunk of chunks) {
        for (let len = 2; len <= 5; len += 1) {
          for (let i = 0; i + len <= chunk.length; i += 1) {
            const word = chunk.slice(i, i + len);
            if (isGoodWord(word)) counts.set(word, (counts.get(word) || 0) + 1);
          }
        }
      }
    }
    const earlySet = new Set();
    const earlySentences = sentences.slice(0, Math.ceil(sentences.length / 3));
    for (const s of earlySentences) {
      for (const term of BUSINESS_WHITELIST) {
        if (s.includes(term)) earlySet.add(term);
      }
    }
    const scored = [...counts.entries()]
      .filter(([word, c]) => c >= 2 || (c === 1 && BUSINESS_WHITELIST.has(word)))
      .map(([word, count]) => ({
        word,
        score: count * Math.pow(word.length, 1.3) * (earlySet.has(word) ? 1.5 : 1),
      }))
      .sort((a, b) => b.score - a.score);
    const picked = [];
    for (const item of scored) {
      if (picked.length >= topN) break;
      if (picked.some((p) => p.includes(item.word))) continue;
      const overrideIdx = picked.findIndex((p) => item.word.includes(p) && item.word.length > p.length);
      if (overrideIdx >= 0) { picked[overrideIdx] = item.word; continue; }
      picked.push(item.word);
    }
    return picked;
  }

  function extractSpeakers(sentences) {
    const names = new Set();
    for (const s of sentences) {
      const m = s.match(/^([\u4e00-\u9fa5]{2,4})[：:]/);
      if (m) names.add(m[1]);
    }
    for (const s of sentences) {
      const m = s.match(/([\u4e00-\u9fa5]{2,4})(说|讲|补充|问|回答|汇报|通报)/);
      if (m) names.add(m[1]);
    }
    return [...names];
  }

  function findOwner(sentence, speakers) {
    for (const name of speakers) {
      const idx = sentence.indexOf(name);
      if (idx === -1) continue;
      const after = sentence.slice(idx + name.length, idx + name.length + 5);
      if (/^(负责|牵头|跟进|来|那边|这边|会|说|讲|补充|应|要|去|做|写|交|给|出|完成)/.test(after)) return name;
    }
    const head = sentence.match(/^([\u4e00-\u9fa5]{2,4})[：:]/);
    if (head) return head[1];
    const assign = sentence.match(/([\u4e00-\u9fa5]{2,4})(负责|牵头|跟进|推进|来(?:做|写|处理|对接))/);
    if (assign) return assign[1];
    return '';
  }

  const DECISION_RE = /(决定|确定|定了|定下来|统一|结论|原则上|敲定|拍板|一致认为|达成一致|达成了|就这么|通过了|最终定|那[就 ]?定[了 ]|明确了|确认了|大家同意|没有异议|无异议|就这样|按这个)/;
  const ACTION_RE = /(负责|牵头|跟进|推进|落地|整理|输出|对接|排期|同步给|下发|上线|部署|评审|拉一个|出一个|给到|需要做|需要|要做|去做|完成|交付|提交|发起|安排|协调|沟通)/;
  const DONE_RE = /(已经|已完成|做完了|做好了|搞定了|弄完了|上次|上个月|上周)/;
  const RISK_RE = /(风险|问题|阻塞|卡住|延期|推迟|延后|往后推|担心|难点|缺少|不足|不确定|没定|未定|有困难|来不及|赶不上|不太清楚|还不知道|还没定|待确认|有争议|有分歧)/;
  const SMALL_TALK_RE = /(开始今天的|人到齐|散会|谢谢大家|大家辛苦|听得见吗|测试一下|那我们开始|开始吧|结束了|好了好了|再见|拜拜|没事|没关系)/;
  const DUE_RE = /((?:下+周|本?周)[一二三四五六日天]?|今天|明天|后天|月底|月初|下个?月|本周内|下周内|\d{1,2}月\d{1,2}[日号]|\d{1,2}[日号]前?|两周内|一周内|三天内|\d+天内|中旬|下旬|上半月|下半月|年底|年末|年前|节前|年前)/;

  function findDue(sentence) {
    const m = sentence.match(DUE_RE);
    return m ? m[1] : '';
  }

  function localSummary(text, meta) {
    const sentences = splitSentences(text);
    const keywords = extractKeywords(sentences, 8);
    const speakers = extractSpeakers(sentences);
    const decisions = [], actions = [], risks = [], discussItems = [];

    for (const s of sentences) {
      const clean = s.replace(/^[\u4e00-\u9fa5]{2,4}[：:]\s*/, '').trim();
      if (clean.length < 8) {
        if (DECISION_RE.test(clean) && decisions.length < 6) decisions.push(clean);
        continue;
      }
      if (SMALL_TALK_RE.test(clean)) continue;
      let categorized = false;
      if (RISK_RE.test(clean) && risks.length < 8) { risks.push(clean); categorized = true; }
      if (!categorized && DECISION_RE.test(clean) && decisions.length < 8) { decisions.push(clean); categorized = true; }
      if (!categorized) {
        if (ACTION_RE.test(clean) && !DONE_RE.test(clean) && !/^(?:我)?建议/.test(clean) && actions.length < 10) {
          actions.push({ task: clean, owner: findOwner(s, speakers), due: findDue(clean) });
          categorized = true;
        }
      }
      if (!categorized) discussItems.push(clean);
    }

    const groups = groupByTopic(sentences, keywords);
    const topic = (meta.topic && meta.topic.trim()) || (keywords.length >= 2 ? `${keywords[0]}与${keywords[1]}专题会` : '会议纪要');
    const summary = buildSummary(sentences, keywords, decisions, actions, risks);

    return { topic, summary, sections: groups, decisions, actions: dedupeActions(actions), risks, keywords, _source: 'local' };
  }

  function buildSummary(sentences, keywords, decisions, actions, risks) {
    const parts = [];
    parts.push(`本次记录共 ${sentences.length} 句。`);
    if (keywords.length) parts.push(`讨论集中在 ${keywords.slice(0, 4).join('、')} 等方面。`);
    if (decisions.length) parts.push(`形成 ${decisions.length} 项明确结论，`);
    if (actions.length) parts.push(`识别出 ${actions.length} 项待办事项。`);
    if (risks.length) parts.push(`另有 ${risks.length} 处风险或待确认事项。`);
    return parts.join('');
  }

  function dedupeActions(actions) {
    const seen = new Set();
    return actions.filter((a) => { const key = a.task.slice(0, 14); if (seen.has(key)) return false; seen.add(key); return true; });
  }

  function groupByTopic(sentences, keywords) {
    if (!sentences.length) return [];
    const topicAnchors = keywords.slice(0, 5);
    const groups = [];
    const anchoredIndices = new Set();
    if (topicAnchors.length >= 2) {
      for (const kw of topicAnchors) {
        const matched = sentences.map((s, i) => ({ s, i })).filter(({ s, i }) => !anchoredIndices.has(i) && s.includes(kw));
        if (matched.length >= 2) {
          for (const { i } of matched) anchoredIndices.add(i);
          const points = matched.map(({ s }) => s.replace(/^[\u4e00-\u9fa5]{2,4}[：:]\s*/, '').trim()).filter((s) => s.length >= 8 && !SMALL_TALK_RE.test(s)).slice(0, 5);
          if (points.length >= 2) groups.push({ title: `关于${kw}`, points });
        }
      }
    }
    const unanchored = sentences.filter((_, i) => !anchoredIndices.has(i));
    if (unanchored.length > 0 && groups.length < 6) {
      const remainingSlots = 6 - groups.length;
      const target = Math.min(remainingSlots, Math.max(1, Math.round(unanchored.length / 4)));
      const size = Math.ceil(unanchored.length / target);
      for (let i = 0; i < unanchored.length && groups.length < 6; i += size) {
        const chunk = unanchored.slice(i, i + size);
        const points = chunk.map((s) => s.replace(/^[\u4e00-\u9fa5]{2,4}[：:]\s*/, '').trim()).filter((s) => s.length >= 8 && !SMALL_TALK_RE.test(s)).slice(0, 4);
        if (!points.length) continue;
        const kws = extractKeywords(chunk, 2);
        groups.push({ title: kws.length ? kws.join(' · ') : points[0].slice(0, 16), points });
      }
    }
    return groups.slice(0, 6);
  }

  /* ---------------- 生成纪要 ---------------- */
  async function summarize() {
    const text = els.transcript.value.trim();
    if (text.length < 40) { toast('会议内容太短，至少 40 字'); return; }
    const useLlm = state.engine !== 'local' && state.cap.llm;
    els.btnSummarize.disabled = true;
    els.result.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在生成纪要…</span></div>';
    setStatus('生成中', 'status-run');
    try {
      let doc;
      if (useLlm) {
        const resp = await fetch('/api/summarize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, mode: 'auto' }) });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
        doc = data;
      } else {
        doc = localSummary(text, state.meta);
      }
      state.doc = doc;
      renderDoc(doc);
      saveHistory(doc, text);
      els.btnCopy.disabled = false;
      els.btnExport.disabled = false;
      els.engineTag.textContent = doc._source === 'llm' ? `大模型生成${doc._truncated ? '（原文超长已抽样）' : ''}` : '本地规则生成';
      setStatus('完成', 'status-ok');
    } catch (e) {
      els.result.innerHTML = `<div class="empty"><div class="empty-icon">!</div><p>${escapeHtml(e.message)}</p><p class="muted">已自动改用本地规则生成</p></div>`;
      const doc = localSummary(text, state.meta);
      state.doc = doc;
      renderDoc(doc);
      saveHistory(doc, text);
      els.btnCopy.disabled = false;
      els.btnExport.disabled = false;
      els.engineTag.textContent = '本地规则生成';
      setStatus('待命', 'status-idle');
    } finally {
      els.btnSummarize.disabled = false;
    }
  }

  /* ---------------- 渲染 ---------------- */
  function renderDoc(doc) {
    const parts = [];
    const topic = doc.topic || '会议纪要';
    parts.push(`<h3 class="doc-title">${escapeHtml(topic)}</h3>`);
    const metaBits = [nowLabel()];
    if (state.meta.members) metaBits.push('参会人：' + state.meta.members);
    parts.push(`<div class="doc-meta">${escapeHtml(metaBits.join(' · '))}</div>`);
    if (doc.summary) parts.push(`<div class="summary-text">${escapeHtml(doc.summary)}</div>`);
    if (Array.isArray(doc.sections) && doc.sections.length) {
      parts.push('<div class="block"><h4>议题要点</h4>');
      for (const sec of doc.sections) {
        parts.push('<div class="section-item">');
        parts.push(`<div class="sec-title">${escapeHtml(sec.title || '讨论')}</div>`);
        parts.push('<ul>');
        for (const p of sec.points || []) parts.push(`<li>${escapeHtml(p)}</li>`);
        parts.push('</ul></div>');
      }
      parts.push('</div>');
    }
    if (Array.isArray(doc.decisions) && doc.decisions.length) {
      parts.push('<div class="block decision"><h4>已定事项</h4><ul class="plain-list">');
      for (const d of doc.decisions) parts.push(`<li>${escapeHtml(d)}</li>`);
      parts.push('</ul></div>');
    }
    if (Array.isArray(doc.actions) && doc.actions.length) {
      parts.push('<div class="block"><h4>待办</h4><table class="action-table"><thead><tr><th>事项</th><th>负责人</th><th>时间</th></tr></thead><tbody>');
      for (const a of doc.actions) {
        parts.push(`<tr><td>${escapeHtml(a.task)}</td><td class="owner">${escapeHtml(a.owner || '待定')}</td><td class="owner">${escapeHtml(a.due || '—')}</td></tr>`);
      }
      parts.push('</tbody></table></div>');
    }
    if (Array.isArray(doc.risks) && doc.risks.length) {
      parts.push('<div class="block warn"><h4>风险与待确认</h4><ul class="plain-list">');
      for (const r of doc.risks) parts.push(`<li>${escapeHtml(r)}</li>`);
      parts.push('</ul></div>');
    }
    if (Array.isArray(doc.keywords) && doc.keywords.length) {
      parts.push('<div class="block"><h4>关键词</h4><div class="chips">');
      for (const k of doc.keywords) parts.push(`<span class="chip">${escapeHtml(k)}</span>`);
      parts.push('</div></div>');
    }
    els.result.innerHTML = parts.join('');
  }

  /* ---------------- 导出 ---------------- */
  function toMarkdown(doc) {
    const lines = [];
    lines.push(`# ${doc.topic || '会议纪要'}`, '');
    const metaBits = [nowLabel()];
    if (state.meta.members) metaBits.push(`参会人：${state.meta.members}`);
    lines.push(`> ${metaBits.join(' · ')}`, '');
    if (doc.summary) lines.push('## 概述', '', doc.summary, '');
    if (doc.sections && doc.sections.length) {
      lines.push('## 议题要点', '');
      for (const sec of doc.sections) {
        lines.push(`### ${sec.title || '讨论'}`);
        for (const p of sec.points || []) lines.push(`- ${p}`);
        lines.push('');
      }
    }
    if (doc.decisions && doc.decisions.length) { lines.push('## 已定事项', ''); for (const d of doc.decisions) lines.push(`- ${d}`); lines.push(''); }
    if (doc.actions && doc.actions.length) {
      lines.push('## 待办', '', '| 事项 | 负责人 | 时间 |', '| --- | --- | --- |');
      for (const a of doc.actions) lines.push(`| ${a.task} | ${a.owner || '待定'} | ${a.due || '—'} |`);
      lines.push('');
    }
    if (doc.risks && doc.risks.length) { lines.push('## 风险与待确认', ''); for (const r of doc.risks) lines.push(`- ${r}`); lines.push(''); }
    if (doc.keywords && doc.keywords.length) lines.push(`**关键词**：${doc.keywords.join('、')}`, '');
    lines.push('---', '', `> 由会议纪要 App 生成 · ${nowLabel()}`);
    return lines.join('\n');
  }

  async function copyMarkdown() {
    if (!state.doc) return;
    const text = toMarkdown(state.doc);
    try {
      await navigator.clipboard.writeText(text);
      toast('已复制 Markdown');
    } catch (e) {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      toast('已复制');
    }
  }

  function exportMarkdown() {
    if (!state.doc) return;
    const blob = new Blob([toMarkdown(state.doc)], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safe = (state.doc.topic || '会议纪要').replace(/[\\/:*?"<>|]/g, '');
    a.href = url;
    a.download = `${safe}-${nowLabel().replace(/[: ]/g, '-')}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  /* ---------------- 历史记录 ---------------- */
  function loadHistory() {
    try { return JSON.parse(localStorage.getItem(STORE_DOCS) || '[]'); } catch (e) { return []; }
  }
  function saveHistory(doc, text) {
    const list = loadHistory();
    list.unshift({ id: Date.now(), time: nowLabel(), topic: doc.topic, doc, text, meta: { ...state.meta } });
    localStorage.setItem(STORE_DOCS, JSON.stringify(list.slice(0, 20)));
  }
  function renderHistory() {
    const list = loadHistory();
    const box = $('historyList');
    if (!list.length) { box.innerHTML = '<div class="empty"><p class="muted">还没有历史纪要</p></div>'; return; }
    box.innerHTML = list.map((item) => `<div class="history-item" data-id="${item.id}">
      <div class="h-title">${escapeHtml(item.topic || '未命名会议')}</div>
      <div class="h-time">${escapeHtml(item.time)}</div>
      <div class="h-sub">${escapeHtml((item.doc && item.doc.summary) || '')}</div>
    </div>`).join('');
    box.querySelectorAll('.history-item').forEach((node) => {
      node.addEventListener('click', () => {
        const item = list.find((x) => String(x.id) === node.dataset.id);
        if (!item) return;
        els.transcript.value = item.text || '';
        updateCount();
        state.doc = item.doc;
        state.meta = item.meta || { topic: '', members: '' };
        renderDoc(item.doc);
        els.btnCopy.disabled = false;
        els.btnExport.disabled = false;
        els.engineTag.textContent = item.doc && item.doc._source === 'llm' ? '大模型生成' : '本地规则生成';
        closeHistory();
      });
    });
  }

  /* ---------------- 弹层 ---------------- */
  function openSettings() {
    $('settingsModal').hidden = false;
    $('inputTopic').value = state.meta.topic;
    $('inputMembers').value = state.meta.members;
    renderCapability();
  }
  function closeSettings() {
    state.meta.topic = $('inputTopic').value.trim();
    state.meta.members = $('inputMembers').value.trim();
    localStorage.setItem(STORE_META, JSON.stringify(state.meta));
    $('settingsModal').hidden = true;
  }
  function openHistory() { renderHistory(); $('historyDrawer').hidden = false; }
  function closeHistory() { $('historyDrawer').hidden = true; }

  function renderCapability() {
    const set = (id, ok, onText, offText, cls) => {
      const el = $(id);
      el.textContent = ok ? onText : offText;
      el.className = ok ? (cls || 'on') : 'off';
    };
    set('capLive', state.cap.live, '可用', '不支持');
    set('capAsr', state.cap.asr, '已配置', '未配置');
    set('capLlm', state.cap.llm, '已配置', '未配置');
    set('capLocalAsr', state.cap.localAsr, state.cap.localModelLoaded ? '已就绪' : '可安装', '未安装', state.cap.localModelLoaded ? 'on' : 'warn');
  }

  /* ---------------- 初始化 ---------------- */
  async function detectCapability() {
    state.cap.live = !!SR;
    try {
      const resp = await fetch('/api/config', { cache: 'no-store' });
      if (resp.ok) {
        const data = await resp.json();
        state.cap.asr = !!data.asr;
        state.cap.llm = !!data.llm;
        if (data.local_asr) {
          state.cap.localAsr = data.local_asr.available;
          state.cap.localModelLoaded = data.local_asr.loaded;
        }
      }
    } catch (e) {
      state.cap.asr = false;
      state.cap.llm = false;
      state.cap.localAsr = false;
      state.cap.localModelLoaded = false;
    }
    renderCapability();

    // 推荐模式
    if (state.cap.localAsr) {
      els.hint.textContent = '本地引擎就绪：录音后本机转写，完全免费、隐私安全';
      if (!$('asrEngineSwitch_local')) {
        // 确保默认 asrEngine 设置为 local（如果可用）
        state.asrEngine = 'auto';
      }
    } else if (state.cap.asr) {
      els.hint.textContent = '在线引擎就绪：录音后上传转写';
    } else if (SR) {
      els.hint.textContent = '本地模式：浏览器实时识别（需网络）';
    } else {
      els.hint.textContent = '本地模式：可直接粘贴文字后生成纪要';
    }
  }

  function bindEvents() {
    els.btnRecord.addEventListener('click', () => {
      if (state.recording) stopRecording(false);
      else startRecording();
    });

    $('modeSwitch').addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn || state.recording) return;
      state.mode = btn.dataset.mode;
      $('modeSwitch').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === btn));
      const engineLabel = state.cap.localAsr ? '本地' : (state.cap.asr ? '在线' : '浏览器');
      els.hint.textContent = state.mode === 'live' ? '点击开始，边说边转成文字' : `点击开始录音，停止后自动用${engineLabel}引擎转写`;
      els.liveText.textContent = state.mode === 'live' ? '等待开始…' : '录音模式下，转写结果会直接写入下方文本';
    });

    $('engineSwitch').addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      state.engine = btn.dataset.engine;
      $('engineSwitch').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === btn));
      if (state.engine === 'auto' && !state.cap.llm) {
        toast('未配置大模型，将使用本地规则生成纪要');
      }
    });

    // ASR 引擎切换
    const asrSwitch = $('asrEngineSwitch');
    if (asrSwitch) {
      asrSwitch.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn || state.recording) return;
        state.asrEngine = btn.dataset.asr;
        $('asrEngineSwitch').querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === btn));
        const labels = { auto: '自动', local: '本地', online: '在线', browser: '浏览器' };
        toast(`语音引擎已切换为：${labels[state.asrEngine] || state.asrEngine}`);
      });
    }

    els.transcript.addEventListener('input', updateCount);
    els.btnCorrect.addEventListener('click', correctText);
    els.btnSummarize.addEventListener('click', summarize);
    els.btnCopy.addEventListener('click', copyMarkdown);
    els.btnExport.addEventListener('click', exportMarkdown);

    $('btnClear').addEventListener('click', () => {
      if (!els.transcript.value) return;
      els.transcript.value = '';
      updateCount();
      els.liveText.textContent = '等待开始…';
    });

    $('btnSample').addEventListener('click', () => {
      els.transcript.value = SAMPLE;
      updateCount();
      toast('已填入示例会议内容');
    });

    $('btnSettings').addEventListener('click', openSettings);
    $('btnCloseSettings').addEventListener('click', closeSettings);
    $('btnOkSettings').addEventListener('click', closeSettings);
    $('btnHistory').addEventListener('click', openHistory);
    $('btnCloseHistory').addEventListener('click', closeHistory);

    $('settingsModal').addEventListener('click', (e) => { if (e.target === $('settingsModal')) closeSettings(); });
    $('historyDrawer').addEventListener('click', (e) => { if (e.target === $('historyDrawer')) closeHistory(); });

    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); summarize(); }
    });
  }

  function init() {
    try {
      state.meta = JSON.parse(localStorage.getItem(STORE_META) || '{}') || { topic: '', members: '' };
    } catch (e) { state.meta = { topic: '', members: '' }; }
    state.meta.topic = state.meta.topic || '';
    state.meta.members = state.meta.members || '';
    bindEvents();
    updateCount();
    detectCapability();
  }

  init();
})();