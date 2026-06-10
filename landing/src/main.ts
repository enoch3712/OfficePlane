/* ===== OfficePlane landing — interactions ===== */
import './landing.css'

/* ---- scroll reveal ---- */
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) {
      e.target.classList.add('show')
      io.unobserve(e.target)
    }
  })
}, { threshold: 0.14 })
document.querySelectorAll('.reveal').forEach((el) => io.observe(el))

/* ---- hero run card: stream the steps, then verify ---- */
function playRun(): void {
  const steps = document.querySelectorAll<HTMLElement>('#steps .step')
  const banner = document.getElementById('verifyBanner')
  if (!banner) return
  steps.forEach((s) => s.classList.remove('in'))
  banner.classList.remove('in')
  steps.forEach((s, i) => {
    setTimeout(() => s.classList.add('in'), 350 + i * 520)
  })
  setTimeout(() => banner.classList.add('in'), 350 + steps.length * 520 + 250)
}
const runCard = document.getElementById('runCard')
let ran = false
const runIO = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting && !ran) { ran = true; playRun() }
  })
}, { threshold: 0.4 })
if (runCard) runIO.observe(runCard)
// loop the run demo
setInterval(() => { if (ran) playRun() }, 7200)

/* ---- round-trip packet animation ---- */
function spawnPacket(lane: HTMLElement, cls: string, fromLeft: boolean, dur: number): void {
  const p = document.createElement('div')
  p.className = 'rt-packet ' + cls
  lane.appendChild(p)
  const start = fromLeft ? 0 : 100
  const end = fromLeft ? 100 : 0
  const t0 = performance.now()
  function frame(now: number): void {
    const k = Math.min((now - t0) / dur, 1)
    p.style.left = (start + (end - start) * k) + '%'
    p.style.opacity = String(k < 0.1 ? k * 10 : (k > 0.9 ? (1 - k) * 10 : 1))
    if (k < 1) requestAnimationFrame(frame)
    else p.remove()
  }
  requestAnimationFrame(frame)
}

// "bad" lane: many sequential round trips
const laneBad = document.getElementById('laneBad')
const badCount = document.getElementById('badCount')
function runBad(): void {
  if (!laneBad || !badCount) return
  let n = 0
  badCount.textContent = '0'
  const trips = 6
  let i = 0
  function trip(): void {
    if (i >= trips) {
      setTimeout(runBad, 1400)
      return
    }
    spawnPacket(laneBad!, 'o', true, 600)   // out
    setTimeout(() => {
      spawnPacket(laneBad!, 'o', false, 600) // back
      setTimeout(() => { n++; badCount!.textContent = String(n); i++; trip() }, 640)
    }, 640)
  }
  trip()
}

// "good" lane: one request, one verified response
const laneGood = document.getElementById('laneGood')
const goodCount = document.getElementById('goodCount')
function runGood(): void {
  if (!laneGood || !goodCount) return
  goodCount.textContent = '1'
  spawnPacket(laneGood, 'o', true, 700)
  setTimeout(() => {
    spawnPacket(laneGood!, 'g', false, 700)
  }, 1600)
  setTimeout(runGood, 4200)
}

const rtBad = document.getElementById('rtBad')
const rtIO = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) {
      runBad()
      runGood()
      rtIO.disconnect()
    }
  })
}, { threshold: 0.3 })
if (rtBad) rtIO.observe(rtBad)

/* ---- perf bars fill on reveal ---- */
const perf = document.querySelector('.perf')
if (perf) {
  const perfIO = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        document.querySelectorAll<HTMLElement>('.pr-fill').forEach((f) => {
          f.style.width = f.dataset.w ?? ''
        })
        perfIO.disconnect()
      }
    })
  }, { threshold: 0.4 })
  perfIO.observe(perf)
}

/* ---- copy command ---- */
const copyBtn = document.getElementById('copyCmd')
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    navigator.clipboard?.writeText('git clone https://github.com/officeplane/officeplane && docker compose up -d')
    const old = copyBtn.textContent
    copyBtn.textContent = 'copied ✓'
    copyBtn.style.color = 'var(--green)'
    setTimeout(() => { copyBtn.textContent = old; copyBtn.style.color = '' }, 1600)
  })
}
