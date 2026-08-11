// Web Audio API Synthesizer for Robotic Servo Motors & Metallic Mechanics

class ServoAudioEngine {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;
  private servoOsc: OscillatorNode | null = null;
  private servoGain: GainNode | null = null;

  private init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    if (muted && this.servoGain) {
      this.servoGain.gain.setTargetAtTime(0, this.ctx?.currentTime || 0, 0.05);
    }
  }

  public toggleMute(): boolean {
    this.setMuted(!this.isMuted);
    return this.isMuted;
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  // Play a realistic mechanical click when joints move or buttons are clicked
  public playClick(freq = 800, duration = 0.03) {
    if (this.isMuted) return;
    this.init();
    if (!this.ctx) return;

    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(120, this.ctx.currentTime + duration);

      gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch {
      // AudioContext policy fallback
    }
  }

  // Play continuous servo rotation hum tied to speed / intensity
  public updateServoSound(intensity: number, speed: number) {
    if (this.isMuted || intensity <= 0.01) {
      if (this.servoGain && this.ctx) {
        this.servoGain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.1);
      }
      return;
    }

    this.init();
    if (!this.ctx) return;

    try {
      if (!this.servoOsc) {
        this.servoOsc = this.ctx.createOscillator();
        this.servoGain = this.ctx.createGain();

        // Sawtooth / Square mix for motor gear noise
        this.servoOsc.type = 'sawtooth';
        this.servoOsc.frequency.setValueAtTime(140, this.ctx.currentTime);
        this.servoGain.gain.setValueAtTime(0, this.ctx.currentTime);

        this.servoOsc.connect(this.servoGain);
        this.servoGain.connect(this.ctx.destination);
        this.servoOsc.start();
      }

      const baseFreq = 120 + Math.abs(speed) * 80 + intensity * 60;
      this.servoOsc.frequency.setTargetAtTime(baseFreq, this.ctx.currentTime, 0.05);

      const targetGain = Math.min(0.06, intensity * 0.04);
      this.servoGain.gain.setTargetAtTime(targetGain, this.ctx.currentTime, 0.05);
    } catch {
      // Audio policy catch
    }
  }

  // Play hand clasp / metallic lock chime
  public playClaspChime() {
    if (this.isMuted) return;
    this.init();
    if (!this.ctx) return;

    try {
      const now = this.ctx.currentTime;
      // Dual resonant metallic ping
      [523.25, 659.25, 1046.5].forEach((freq, idx) => {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + idx * 0.04);

        gain.gain.setValueAtTime(0.08, now + idx * 0.04);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.04 + 0.3);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now + idx * 0.04);
        osc.stop(now + idx * 0.04 + 0.3);
      });
    } catch {
      // Audio catch
    }
  }

  // Glitch / Spark sound effect for overload mode
  public playSparkGlitch() {
    if (this.isMuted) return;
    this.init();
    if (!this.ctx) return;

    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'square';
      osc.frequency.setValueAtTime(1200 + Math.random() * 800, now);
      osc.frequency.linearRampToValueAtTime(200, now + 0.08);

      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.08);
    } catch {
      // Catch
    }
  }
}

export const soundEngine = new ServoAudioEngine();
