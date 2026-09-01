// La libreria è pubblicata come bundle CJS: importiamo l'intero modulo
// e recuperiamo le classi sia che jsDelivr le esponga come export
// nominati, sia che finiscano tutte dentro "default".
const _mod = await import('https://cdn.jsdelivr.net/npm/anime4k-webgpu/+esm');
const Anime4K = (_mod.default && Object.keys(_mod.default).length) ? _mod.default : _mod;
const { ModeA, ModeB, ModeC, ModeAA, ModeBB, ModeCA, render } = Anime4K;

const statusEl = document.getElementById('status');

if (!ModeA || !render) {
    if (statusEl) {
        statusEl.textContent =
            '❌ La libreria anime4k-webgpu non ha esposto le classi attese (ModeA/render). Export disponibili: ' +
            Object.keys(Anime4K).join(', ');
    }
    throw new Error('Export mancanti in anime4k-webgpu');
}

const srcVideo = document.getElementById('mainVideo');
const mainCanvas = document.getElementById('mainCanvas');
const playerWrap = document.getElementById('playerWrap');
const playPauseBtn = document.getElementById('playPauseBtn');
const fullscreenBtn = document.getElementById('fullscreenBtn');
const modeSelect = document.getElementById('modeSelect');
const resolutionSelect = document.getElementById('resolutionSelect');
const modeDesc = document.getElementById('modeDesc');
const seekBar = document.getElementById('seekBar');
const timeLabel = document.getElementById('timeLabel');
const upscalerControlls = document.getElementById('upscalerControlls');
const fastSeekIndicator = document.getElementById('fastSeekIndicator');

// Recupera le preferenze salvate in localStorage e applicale ai controlli
const savedMode = localStorage.getItem('upscalerMode');
const savedResolution = localStorage.getItem('upscalerResolution');
if (savedMode) {
    modeSelect.value = savedMode;
    modeSelect.dispatchEvent(new Event('change')); // Lancia manualmente gli eventi di cambio per avviare la pipeline con i valori caricati
}
if (savedResolution) {
    resolutionSelect.value = savedResolution;
    resolutionSelect.dispatchEvent(new Event('change')); // Lancia manualmente gli eventi di cambio per avviare la pipeline con i valori caricati
}

// Canvas di back-end per il rendering WebGPU (nascosto)
const backendCanvas = document.createElement('canvas');
backendCanvas.style.display = 'none';
document.body.appendChild(backendCanvas);

const MODES = [
    { name: 'A',  cls: ModeA,  desc: 'Restauro leggero + upscaling CNN. Bilanciata, buon punto di partenza.' },
    { name: 'B',  cls: ModeB,  desc: 'Variante orientata alla morbidezza dei dettagli.' },
    { name: 'C',  cls: ModeC,  desc: 'Upscaling con enfasi sui bordi, meno restauro.' },
    { name: 'AA', cls: ModeAA, desc: 'Qualità più alta (doppio passaggio), più pesante per la GPU.' },
    { name: 'BB', cls: ModeBB, desc: 'Doppio passaggio orientato alla morbidezza, alta qualità.' },
    { name: 'CA', cls: ModeCA, desc: 'Combinazione ad alta qualità, la più pesante.' },
];

let currentGeneration = 0;
let isPlaying = false;
let isDraggingSeek = false;
let animationFrameId = null;
let clickTimer = null;
let seekAccumulator = 0;
let seekTimer = null;

function setStatus(msg, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.style.color = isError ? '#ff6b6b' : '#eee';
}

function fmtTime(s) {
    if (!isFinite(s) || s < 0) return '00:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
}

function updateModeLabel() {
    if (!modeDesc) return;
    if (modeSelect.value === 'off') {
        modeDesc.textContent = '📴 Upscaling disattivato: il video mostra la sorgente originale.';
        return;
    }
    const idx = parseInt(modeSelect.value, 10);
    if (idx >= 0 && idx < MODES.length) {
        modeDesc.textContent = '📌 ' + MODES[idx].desc;
    }
}
updateModeLabel();

function getTargetResolution() {
    const val = resolutionSelect ? resolutionSelect.value : 'originale';
    if (val === '1080p') return { width: 1920, height: 1080 };
    if (val === '4k') return { width: 3840, height: 2160 };
    return null; // originale
}

// Aggiorna la visibilità di canvas/video in base alla modalità
function updateDisplayMode() {
    const isOff = modeSelect.value === 'off';
    if (playerWrap) playerWrap.style.display = isOff ? 'none' : 'block';
    if (upscalerControlls) upscalerControlls.style.display = isOff ? 'none' : 'block';
    if (srcVideo) srcVideo.style.display = isOff ? 'block' : 'none';
}

async function checkWebGPU() {
    if (!('gpu' in navigator)) {
        setStatus('❌ Questo browser non supporta WebGPU. Usa Chrome o Edge aggiornati (versione 113+).', true);
        return false;
    }
    try {
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) {
            setStatus('❌ Nessun adattatore WebGPU disponibile su questo dispositivo.', true);
            return false;
        }
        return true;
    } catch (e) {
        setStatus('❌ Errore WebGPU: ' + e.message, true);
        return false;
    }
}

// Disegna il frame sul canvas principale (copia da backend)
function drawFrame() {
    if (modeSelect.value === 'off') {
        animationFrameId = requestAnimationFrame(drawFrame);
        return;
    }

    const ctx = mainCanvas.getContext('2d');
    if (backendCanvas.width > 0 && backendCanvas.height > 0) {
        if (mainCanvas.width !== backendCanvas.width || mainCanvas.height !== backendCanvas.height) {
            mainCanvas.width = backendCanvas.width;
            mainCanvas.height = backendCanvas.height;
        }
        ctx.drawImage(backendCanvas, 0, 0);
    }

    animationFrameId = requestAnimationFrame(drawFrame);
}

async function startPipeline() {
    currentGeneration++;
    const myGeneration = currentGeneration;

    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }

    updateDisplayMode();

    if (modeSelect.value === 'off') {
        setStatus('📴 Upscaling disattivato — il video mostra la sorgente originale.');
        drawFrame();
        return;
    }

    const ok = await checkWebGPU();
    if (!ok) {
        drawFrame();
        return;
    }

    const modeIndex = parseInt(modeSelect.value, 10);
    if (isNaN(modeIndex) || modeIndex < 0 || modeIndex >= MODES.length) {
        setStatus('❌ Modalità non valida', true);
        drawFrame();
        return;
    }

    const ModeClass = MODES[modeIndex].cls;
    const target = getTargetResolution();
    const vw = srcVideo.videoWidth || 1280;
    const vh = srcVideo.videoHeight || 720;
    let outW = vw;
    let outH = vh;
    if (target) {
        outW = target.width;
        outH = target.height;
    }

    mainCanvas.width = outW;
    mainCanvas.height = outH;
    backendCanvas.width = outW;
    backendCanvas.height = outH;

    setStatus('🔄 Inizializzazione pipeline Anime4K (' + MODES[modeIndex].name + ') a ' + outW + '×' + outH + '...');

    try {
        let renderSuccess = false;

        try {
            await render({
                video: srcVideo,
                canvas: backendCanvas,
                pipelineBuilder: (device, inputTexture) => {
                    const preset = new ModeClass({
                        device,
                        inputTexture,
                        nativeDimensions: { width: vw, height: vh },
                        targetDimensions: { width: outW, height: outH }
                    });
                    return [preset];
                },
            });
            renderSuccess = true;
        } catch (e) {
            console.warn('Approccio 1 fallito:', e);
        }

        if (!renderSuccess) {
            try {
                await render({
                    video: srcVideo,
                    canvas: backendCanvas,
                    mode: modeIndex,
                });
                renderSuccess = true;
            } catch (e) {
                console.warn('Approccio 2 fallito:', e);
            }
        }

        if (!renderSuccess) {
            throw new Error('Tutti i tentativi di render sono falliti');
        }

        if (myGeneration === currentGeneration) {
            setStatus('✅ Upscaling attivo — modalità ' + MODES[modeIndex].name + ' a ' + outW + '×' + outH + '.');
            drawFrame();
        }
    } catch (e) {
        console.error('Errore pipeline:', e);
        if (myGeneration === currentGeneration) {
            setStatus('❌ Errore nella pipeline Anime4K: ' + e.message, true);
            modeSelect.value = 'off';
            updateModeLabel();
            updateDisplayMode();
            drawFrame();
        }
    }
}

// --- Eventi del video sorgente ---

srcVideo.addEventListener('loadedmetadata', () => {
    if (seekBar) seekBar.max = srcVideo.duration || 100;
    if (timeLabel) timeLabel.textContent = fmtTime(0) + ' / ' + fmtTime(srcVideo.duration);
    startPipeline();
});

srcVideo.addEventListener('timeupdate', () => {
    if (!isDraggingSeek && srcVideo.duration) {
        if (seekBar) seekBar.value = srcVideo.currentTime;
        if (timeLabel) timeLabel.textContent = fmtTime(srcVideo.currentTime) + ' / ' + fmtTime(srcVideo.duration);
    }
});

srcVideo.addEventListener('play', () => {
    isPlaying = true;
    if (playPauseBtn) playPauseBtn.textContent = '⏸';
});

srcVideo.addEventListener('pause', () => {
    isPlaying = false;
    if (playPauseBtn) playPauseBtn.textContent = '▶';
});

srcVideo.addEventListener('ended', () => {
    isPlaying = false;
    if (playPauseBtn) playPauseBtn.textContent = '▶';
    if (seekBar) seekBar.value = 0;
    if (timeLabel) timeLabel.textContent = fmtTime(0) + ' / ' + fmtTime(srcVideo.duration);
});

// --- Controlli Barra Player ---

if (playPauseBtn) {
    playPauseBtn.addEventListener('click', () => {
        if (isPlaying) {
            srcVideo.pause();
        } else {
            srcVideo.play().catch(() => {});
        }
    });
}

if (seekBar) {
    const startSeek = () => { isDraggingSeek = true; };
    const endSeek = () => {
        isDraggingSeek = false;
        if (srcVideo.duration) {
            srcVideo.currentTime = parseFloat(seekBar.value);
        }
    };

    seekBar.addEventListener('mousedown', startSeek);
    seekBar.addEventListener('mouseup', endSeek);
    seekBar.addEventListener('touchstart', startSeek);
    seekBar.addEventListener('touchend', endSeek);
    seekBar.addEventListener('input', () => {
        if (srcVideo.duration && timeLabel) {
            const val = parseFloat(seekBar.value);
            timeLabel.textContent = fmtTime(val) + ' / ' + fmtTime(srcVideo.duration);
        }
    });
}

if (modeSelect) {
    modeSelect.addEventListener('change', () => {
        updateModeLabel();
        if (srcVideo.readyState >= 1) {
            startPipeline();
        }
        localStorage.setItem('upscalerMode', modeSelect.value);
    });
}

if (resolutionSelect) {
    resolutionSelect.addEventListener('change', () => {
        if (srcVideo.readyState >= 1 && modeSelect.value !== 'off') {
            startPipeline();
        }
        localStorage.setItem('upscalerResolution', resolutionSelect.value);
    });
}

if (fullscreenBtn && playerWrap) {
    fullscreenBtn.addEventListener('click', () => {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            playerWrap.requestFullscreen().catch(() => {});
        }
    });
}

// --- Gestione Click e Doppio Click (Play/Pause e +/- 10 Secondi) ---

function handlePlayerClick(e, targetElement) {
    const rect = targetElement.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const isRightSide = clickX > rect.width / 2;

    if (e.detail === 1) {
        // Singolo click: Toggle Play/Pause dopo il ritardo
        clickTimer = setTimeout(() => {
            if (isPlaying) {
                srcVideo.pause();
            } else {
                srcVideo.play().catch(() => {});
            }
        }, 250);
    } else if (e.detail >= 2) {
        // Annulla il play/pause del singolo click
        clearTimeout(clickTimer);
        
        // Cancella il timer dell'indicatore precedente per mantenerlo visibile durante i click rapidi
        clearTimeout(seekTimer);

        // Al secondo click (detail === 2) inizializziamo con 10s, ai successivi aggiungiamo 10s
        if (e.detail === 2) {
            seekAccumulator = 10;
        } else {
            seekAccumulator += 10;
        }
        
        // Applica subito l'avanzamento al video
        if (isRightSide) {
            srcVideo.currentTime = Math.min(srcVideo.duration || 0, srcVideo.currentTime + 10);
            fastSeekIndicator.textContent = `+${seekAccumulator}s`;
        } else {
            srcVideo.currentTime = Math.max(0, srcVideo.currentTime - 10);
            fastSeekIndicator.textContent = `-${seekAccumulator}s`;
        }

        // Mostra l'indicatore
        fastSeekIndicator.style.opacity = 1;

        // Aggiorna UI del player
        if (seekBar) seekBar.value = srcVideo.currentTime;
        if (timeLabel) timeLabel.textContent = fmtTime(srcVideo.currentTime) + ' / ' + fmtTime(srcVideo.duration);

        // Nasconde l'indicatore e resetta l'accumulatore solo quando l'utente smette di cliccare
        seekTimer = setTimeout(() => {
            fastSeekIndicator.style.opacity = 0;
            seekAccumulator = 0;
        }, 600);
    }
}

if (mainCanvas) {
    mainCanvas.addEventListener('click', (e) => handlePlayerClick(e, mainCanvas));
}

// --- Controlli da Tastiera ---

window.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    if (e.code === 'Space') {
        e.preventDefault();
        if (isPlaying) {
            srcVideo.pause();
        } else {
            srcVideo.play().catch(() => {});
        }
    } else if (e.code === 'KeyF') {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else if (playerWrap) {
            playerWrap.requestFullscreen().catch(() => {});
        }
    } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        srcVideo.currentTime = Math.max(0, srcVideo.currentTime - 10);
    } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        srcVideo.currentTime = Math.min(srcVideo.duration || 0, srcVideo.currentTime + 10);
    }
});

// --- Gestione Errori e Chiusura ---

srcVideo.addEventListener('error', () => {
    setStatus('❌ Errore caricamento video: ' + (srcVideo.error?.message || 'sconosciuto'), true);
});

if (srcVideo.readyState >= 1) {
    startPipeline();
}

window.addEventListener('beforeunload', () => {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
});

console.log('🎬 Anime4K Video Player inizializzato');