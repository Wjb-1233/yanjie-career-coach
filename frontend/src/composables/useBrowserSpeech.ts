import { onBeforeUnmount, onMounted, readonly, shallowRef } from 'vue'

interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}

interface RecognitionEvent {
  results: ArrayLike<RecognitionResult>
}

interface BrowserRecognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onstart: (() => void) | null
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}

type RecognitionConstructor = new () => BrowserRecognition
interface NativeSpeechBridge {
  startListening(): void
  stopListening(): void
  speak(text: string): void
  stopSpeaking(): void
}
type SpeechWindow = Window & {
  SpeechRecognition?: RecognitionConstructor
  webkitSpeechRecognition?: RecognitionConstructor
  AndroidSpeechBridge?: NativeSpeechBridge
}

export function useBrowserSpeech() {
  const available = shallowRef(false)
  const secureContext = shallowRef(true)
  const listening = shallowRef(false)
  const speaking = shallowRef(false)
  const transcript = shallowRef('')
  const interim = shallowRef('')
  const error = shallowRef('')
  const autoRead = shallowRef(true)
  let recognition: BrowserRecognition | null = null

  const onNativeSpeech: EventListener = (event) => {
    const detail = (event as CustomEvent<{ status: string; value: string }>).detail
    if (!detail) return
    if (detail.status === 'start') listening.value = true
    if (detail.status === 'result') { transcript.value = detail.value.trim(); interim.value = '' }
    if (detail.status === 'interim') interim.value = detail.value.trim()
    if (detail.status === 'error') error.value = detail.value
    if (detail.status === 'end') { listening.value = false; interim.value = '' }
    if (detail.status === 'speaking-start') speaking.value = true
    if (detail.status === 'speaking-end') speaking.value = false
  }

  onMounted(() => {
    const browser = window as SpeechWindow
    available.value = Boolean(browser.AndroidSpeechBridge || browser.SpeechRecognition || browser.webkitSpeechRecognition)
    secureContext.value = Boolean(browser.AndroidSpeechBridge || window.isSecureContext)
    if (browser.AndroidSpeechBridge) window.addEventListener('yanjie:native-speech', onNativeSpeech)
  })

  function start(): void {
    const browser = window as SpeechWindow
    if (browser.AndroidSpeechBridge) {
      stopSpeaking()
      transcript.value = ''
      interim.value = ''
      error.value = ''
      browser.AndroidSpeechBridge.startListening()
      return
    }
    const Constructor = browser.SpeechRecognition || browser.webkitSpeechRecognition
    if (!Constructor) {
      error.value = '当前浏览器不支持网页语音识别，请使用安卓 Chrome，或切换文字模式。'
      return
    }
    stopSpeaking()
    recognition?.abort()
    transcript.value = ''
    interim.value = ''
    error.value = ''
    const instance = new Constructor()
    instance.lang = 'zh-CN'
    instance.continuous = false
    instance.interimResults = true
    instance.onstart = () => { listening.value = true }
    instance.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (!result) continue
        if (result.isFinal) finalText += result[0].transcript
        else interimText += result[0].transcript
      }
      transcript.value = finalText.trim()
      interim.value = interimText.trim()
    }
    instance.onerror = (event) => {
      const messages: Record<string, string> = {
        'not-allowed': '麦克风权限被拒绝。请在 Chrome 网站设置中允许麦克风；若使用局域网 HTTP 地址，请换用 HTTPS 测试地址。',
        'service-not-allowed': '语音识别服务不可用。请检查网络，或切换文字模式。',
        'audio-capture': '没有检测到可用麦克风，请检查手机的麦克风权限。',
        network: '语音识别服务连接失败，请检查手机网络后重试。',
        'no-speech': '没有听到语音，请靠近麦克风再试一次。',
      }
      error.value = messages[event.error] ?? '语音识别没有完成，请重试或切换文字模式。'
    }
    instance.onend = () => {
      listening.value = false
      if (!transcript.value && interim.value) transcript.value = interim.value
      interim.value = ''
      if (recognition === instance) recognition = null
    }
    recognition = instance
    try { instance.start() }
    catch { recognition = null; error.value = '无法启动麦克风，请检查浏览器权限后重试。' }
  }

  function stop(): void {
    const browser = window as SpeechWindow
    if (browser.AndroidSpeechBridge) browser.AndroidSpeechBridge.stopListening()
    else recognition?.stop()
  }

  function stopSpeaking(): void {
    const browser = window as SpeechWindow
    if (browser.AndroidSpeechBridge) browser.AndroidSpeechBridge.stopSpeaking()
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    speaking.value = false
  }

  function speak(text: string): void {
    if (!text.trim()) return
    const browser = window as SpeechWindow
    if (browser.AndroidSpeechBridge) {
      stopSpeaking()
      error.value = ''
      browser.AndroidSpeechBridge.speak(text)
      return
    }
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      error.value = '当前浏览器不支持语音播报，请直接阅读面试官的文字回复。'
      return
    }
    if (listening.value) stop()
    stopSpeaking()
    error.value = ''
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'zh-CN'
    utterance.rate = 1
    const chineseVoice = window.speechSynthesis.getVoices().find((voice) => voice.lang.toLowerCase().startsWith('zh'))
    if (chineseVoice) utterance.voice = chineseVoice
    utterance.onstart = () => { speaking.value = true }
    utterance.onend = () => { speaking.value = false }
    utterance.onerror = () => { speaking.value = false; error.value = '播报失败，可以点击“重播提问”再试。' }
    window.speechSynthesis.speak(utterance)
  }

  onBeforeUnmount(() => {
    if ((window as SpeechWindow).AndroidSpeechBridge) window.removeEventListener('yanjie:native-speech', onNativeSpeech)
    recognition?.abort()
    stopSpeaking()
  })

  return {
    available: readonly(available), secureContext: readonly(secureContext),
    listening: readonly(listening), speaking: readonly(speaking),
    transcript, interim: readonly(interim), error: readonly(error), autoRead,
    start, stop, speak, stopSpeaking,
  }
}
