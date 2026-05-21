class AudioSpectrum {
    constructor(canvasId, audioElementId) {
        this.canvas = document.getElementById(canvasId);
        this.audio = document.getElementById(audioElementId);
        this.ctx = null;
        this.analyser = null;
        this.source = null;
        this.dataArray = null;
        this.animationId = null;
        this.isInitialized = false;
    }

    init() {
        if (this.isInitialized) return;

        try {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.ctx.createAnalyser();
            this.analyser.fftSize = 256;
            this.source = this.ctx.createMediaElementSource(this.audio);
            this.source.connect(this.analyser);
            this.analyser.connect(this.ctx.destination);
            const bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(bufferLength);
            this.isInitialized = true;
            this.animate();
        } catch (error) {
            console.error('Error initializing audio spectrum:', error);
        }
    }

    animate() {
        if (!this.isInitialized) return;

        const canvas = this.canvas;
        const ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth * window.devicePixelRatio;
        canvas.height = canvas.offsetHeight * window.devicePixelRatio;
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        const width = canvas.offsetWidth;
        const height = canvas.offsetHeight;
        
        const draw = () => {
            this.animationId = requestAnimationFrame(draw);
            this.analyser.getByteFrequencyData(this.dataArray);
            ctx.clearRect(0, 0, width, height);
            const barCount = this.dataArray.length;
            const barWidth = (width / barCount) * 2.5;
            const gap = 2;
            let x = 0;
            
            for (let i = 0; i < barCount; i++) {
                const barHeight = (this.dataArray[i] / 255) * height;
                const isLightTheme = document.body.classList.contains('light') || document.body.classList.contains('dashboard-page') && document.body.classList.contains('light');
                
                // Cyan/teal color range (180-200 hue)
                const baseHue = 185;
                const hueVariation = (i / barCount) * 20; // Small variation in cyan range
                const hue = baseHue + hueVariation;
                
                const saturation = 70;
                let lightness;
                
                if (isLightTheme) {
                    // Darker cyan for light theme
                    lightness = 30 + (this.dataArray[i] / 255) * 25;
                } else {
                    // Lighter cyan for dark theme
                    lightness = 50 + (this.dataArray[i] / 255) * 25;
                }
                
                ctx.fillStyle = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
                const radius = barWidth / 2;
                const y = height - barHeight;
                ctx.beginPath();
                ctx.roundRect(x, y, barWidth - gap, barHeight, [radius, radius, 0, 0]);
                ctx.fill();
                x += barWidth;
            }
        };
        
        draw();
    }

    start() {
        if (!this.isInitialized) {
            this.init();
        }
        
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
        
        if (!this.animationId) {
            this.animate();
        }
    }

    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    destroy() {
        this.stop();
        
        if (this.source) {
            this.source.disconnect();
        }
        
        if (this.analyser) {
            this.analyser.disconnect();
        }
        
        if (this.ctx) {
            this.ctx.close();
        }
        
        this.isInitialized = false;
    }
}

const audioSpectrum = new AudioSpectrum('spectrumCanvas', 'audioPlayer');
