// Loading page control function
function initLoadingScreen() {
    const loadingScreen = document.querySelector('.loading-screen');
    const progressBar = document.querySelector('.progress-bar');
    const progressText = document.querySelector('.progress-text .digital-glitch');
    const loadingMessage = document.querySelector('.loading-message');
    const loadingText = document.querySelector('.loading-text');

    if (!loadingScreen || !progressBar || !progressText) return;

    // Check if returning from internal navigation
    const referrer = document.referrer;
    const currentHost = window.location.host;

    // If returning from another page on the same site, don't display loading animation
    if (referrer && referrer.includes(currentHost) && !isPageReload()) {
        loadingScreen.classList.add('hidden');
        loadingScreen.style.display = 'none';
        return;
    }

    // Set character animation effect - restore progressive display effect
    const titleChars = document.querySelectorAll('.loading-title .char');
    titleChars.forEach((char, index) => {
        // Ensure animation is reset
        char.style.animation = 'none';
        char.offsetHeight; // Trigger reflow
        // Don't specify animation parameters, use definitions in CSS
        char.style.animation = '';
    });

    // Dynamic loading dots animation
    const loadingDots = document.querySelectorAll('.loading-dots .dot');
    loadingDots.forEach((dot, index) => {
        dot.style.animation = 'none';
        dot.offsetHeight; // Trigger reflow
        dot.style.animation = `dot-fade 1.4s infinite ${index * 0.2}s`;
    });

    const messages = [
        "Initializing system components...",
        "Connecting to neural network...",
        "Loading AI modules...",
        "Calibrating response patterns...",
        "Starting quantum processors..."
    ];

    let progress = 0;
    const totalDuration = 5000; // Complete loading in 3.5 seconds
    const interval = 30; // Update every 50ms
    const steps = totalDuration / interval;
    const increment = 100 / steps;

    // Random message update
    let messageIndex = 0;

    const updateProgress = () => {
        progress += increment;

        // Add some randomness to simulate real loading
        const randomFactor = Math.random() * 0.5;
        const adjustedProgress = Math.min(progress + randomFactor, 100);

        // Update progress bar width
        progressBar.style.width = `${adjustedProgress}%`;

        // Update progress text
        const displayProgress = Math.floor(adjustedProgress);
        progressText.textContent = `${displayProgress}%`;

        // Show different messages at different stages
        if (displayProgress > messageIndex * 25 && messageIndex < messages.length) {
            loadingMessage.textContent = messages[messageIndex];
            messageIndex++;

            // Add blinking effect
            loadingScreen.style.filter = 'brightness(1.2)';
            setTimeout(() => {
                loadingScreen.style.filter = 'brightness(1)';
            }, 100);
        }

        // Simulate network loading changes
        if (displayProgress >= 99.5) {
            // Loading complete, hide loading screen
            setTimeout(() => {
                loadingScreen.classList.add('hidden');

                // Completely hide and remove from DOM
                setTimeout(() => {
                    loadingScreen.style.display = 'none';
                }, 500);
            }, 200);
            return;
        }

        // Add random glitch effect
        if (Math.random() < 0.1) {
            createGlitchEffect();
        }

        requestAnimationFrame(updateProgress);
    };

    // Create glitch effect
    const createGlitchEffect = () => {
        // Screen shake
        loadingScreen.style.transform = `translate(${(Math.random() - 0.5) * 10}px, ${(Math.random() - 0.5) * 5}px)`;

        // Random color and opacity adjustment
        loadingScreen.style.filter = `hue-rotate(${Math.random() * 30}deg) brightness(${1 + Math.random() * 0.3})`;

        // Restore normal
        setTimeout(() => {
            loadingScreen.style.transform = 'translate(0, 0)';
            loadingScreen.style.filter = 'none';
        }, 100);
    };

    // Start updating progress - reduce delay, start progress bar display faster
    setTimeout(() => {
        updateProgress();
    }, 300);
}

// Generate random particles dynamically
function createRandomParticle() {
    const container = document.querySelector('.particle-container');

    if (!container) return;

    setInterval(() => {
        const particle = document.createElement('div');
        particle.className = 'particle';

        // Random position
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.top = '100%';

        // Random size
        const size = Math.random() * 2 + 1;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;

        // Get CSS variables
        const styles = getComputedStyle(document.documentElement);
        const colorOptions = [
            styles.getPropertyValue('--accent-green').trim(),
            styles.getPropertyValue('--accent-color-5').trim(),
            styles.getPropertyValue('--accent-blue').trim(),
            styles.getPropertyValue('--accent-color-1').trim()
        ];

        // Random color
        const randomColor = colorOptions[Math.floor(Math.random() * colorOptions.length)];
        particle.style.backgroundColor = randomColor;
        particle.style.boxShadow = `0 0 5px ${randomColor}`;

        // Random opacity
        particle.style.opacity = (Math.random() * 0.5 + 0.3).toString();

        // Add to container
        container.appendChild(particle);

        // Remove element after animation ends
        setTimeout(() => {
            particle.remove();
        }, 5000);
    }, 600); // Create a new particle every 600ms
}

// Add theme options animation effect
function animateThemeOptions() {
    const themeOptions = document.querySelectorAll('.theme-option');
    themeOptions.forEach((option) => {
        // Only control show/hide, let CSS handle animation
        option.style.opacity = '1';
    });
}

// Initialize video player interaction
function initVideoPlayer() {
    const video = document.getElementById('manus-video');
    const videoWrapper = document.querySelector('.manus-video-wrapper');
    const progressContainer = document.querySelector('.manus-video-wrapper .video-progress-container');
    const progressBar = document.querySelector('.manus-video-wrapper .video-progress-bar');
    const playBtn = document.getElementById('video-play-btn');
    const muteBtn = document.getElementById('video-mute-btn');
    const fullscreenBtn = document.getElementById('video-fullscreen-btn');

    if (!video || !videoWrapper) return;

    // Set fixed playback rate to ensure consistent playback speed
    video.playbackRate = 1.0;

    // Ensure video buffer is sufficient
    video.preload = "auto";

    // Handle video buffering to ensure smooth playback
    let bufferingDetected = false;
    let lastPlayPos = 0;
    let currentPlayPos = 0;
    let checkBufferInterval = null;

    // Detect buffer status
    function checkBuffer() {
        currentPlayPos = video.currentTime;

        // Detect if buffering (playback position hasn't changed but video isn't paused)
        const buffering = !video.paused && currentPlayPos === lastPlayPos && !video.ended;

        if (buffering && !bufferingDetected) {
            bufferingDetected = true;
            videoWrapper.classList.add('buffering');
        }

        if (!buffering && bufferingDetected) {
            bufferingDetected = false;
            videoWrapper.classList.remove('buffering');
        }

        lastPlayPos = currentPlayPos;
    }

    // Handle fullscreen change events
    document.addEventListener('fullscreenchange', function () {
        if (!document.fullscreenElement) {
            videoWrapper.classList.remove('fullscreen-active');

            // Restore styles when exiting fullscreen
            videoWrapper.style.borderRadius = '8px';
            videoWrapper.style.boxShadow = '0 0 20px rgba(0, 128, 255, 0.5)';
            videoWrapper.style.margin = '20px auto 30px auto';
            video.style.objectFit = 'contain';
        }
    });

    // Ensure correct video ratio
    function updateVideoSize() {
        // Only adjust size in non-fullscreen mode
        if (document.fullscreenElement) return;

        // Set video element style
        video.style.width = '100%';
        video.style.height = '100%';
        video.style.objectFit = 'contain';
    }

    // Update size after video metadata loads
    video.addEventListener('loadedmetadata', updateVideoSize);

    // If video already has metadata, update size immediately
    if (video.readyState >= 1) {
        updateVideoSize();
    }

    // Use requestAnimationFrame to optimize video progress bar updates
    let animationId = null;
    let lastProgress = 0;

    function updateProgressBar() {
        if (progressBar && !video.paused) {
            // Calculate current actual progress
            const currentProgress = (video.currentTime / video.duration) * 100;

            // Smooth interpolation to reduce stuttering
            const smoothProgress = lastProgress + (currentProgress - lastProgress) * 0.5;
            lastProgress = smoothProgress;

            // Use transform3d to force GPU acceleration
            progressBar.style.width = `${smoothProgress}%`;
        }
        animationId = requestAnimationFrame(updateProgressBar);
    }

    // Start progress bar update when playback begins
    video.addEventListener('play', function () {
        // Reset last progress to ensure smooth transition
        lastProgress = (video.currentTime / video.duration) * 100;

        // Start animation frame updates
        cancelAnimationFrame(animationId);
        animationId = requestAnimationFrame(updateProgressBar);
    });

    // Stop progress bar updates when paused, but update final position
    video.addEventListener('pause', function () {
        cancelAnimationFrame(animationId);
        // Update to accurate position
        if (progressBar) {
            lastProgress = (video.currentTime / video.duration) * 100;
            progressBar.style.width = `${lastProgress}%`;
        }
    });

    // Stop progress bar updates when video ends, but update to 100%
    video.addEventListener('ended', function () {
        cancelAnimationFrame(animationId);
        // Show completed state
        if (progressBar) {
            lastProgress = 100;
            progressBar.style.width = '100%';
        }
    });

    // Sync position on time update (handles video seeking)
    video.addEventListener('timeupdate', function () {
        if (video.paused && progressBar) {
            lastProgress = (video.currentTime / video.duration) * 100;
            progressBar.style.width = `${lastProgress}%`;
        }
    });

    // Ensure updates stop when page is not visible
    document.addEventListener('visibilitychange', function () {
        if (document.hidden && animationId) {
            cancelAnimationFrame(animationId);
        } else if (!document.hidden && !video.paused) {
            animationId = requestAnimationFrame(updateProgressBar);
        }
    });

    // Try to auto-play video
    video.play().catch(e => {
        videoWrapper.classList.add('awaiting-interaction');
    });

    // Replay video when it ends
    video.addEventListener('ended', function () {
        video.currentTime = 0;
        video.play().catch(e => {
            playBtn.innerHTML = '<i class="fas fa-play"></i>';
        });
    });

    // Click video area to play/pause
    videoWrapper.addEventListener('click', function (e) {
        // Avoid triggering when clicking control buttons
        if (e.target.closest('.video-controls')) return;

        if (video.paused) {
            video.play().then(() => {
                playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                videoWrapper.classList.remove('awaiting-interaction');
            }).catch(e => {
                console.log('Playback failed:', e);
            });
        } else {
            video.pause();
            playBtn.innerHTML = '<i class="fas fa-play"></i>';
        }
    });

    // Play/pause button
    playBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (video.paused) {
            video.play().then(() => {
                playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                videoWrapper.classList.remove('awaiting-interaction');
            }).catch(e => {
                console.log('Playback failed:', e);
            });
        } else {
            video.pause();
            playBtn.innerHTML = '<i class="fas fa-play"></i>';
        }
    });

    // Mute button
    muteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        video.muted = !video.muted;
        if (video.muted) {
            muteBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
        } else {
            muteBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
        }
    });

    // Fullscreen button
    fullscreenBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!document.fullscreenElement) {
            // Add fullscreen marker class
            videoWrapper.classList.add('fullscreen-active');

            // Enter fullscreen
            if (video.requestFullscreen) {
                video.requestFullscreen();
            } else if (video.webkitRequestFullscreen) {
                video.webkitRequestFullscreen();
            } else if (video.msRequestFullscreen) {
                video.msRequestFullscreen();
            }
        } else {
            // Exit fullscreen
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        const rect = videoWrapper.getBoundingClientRect();
        const isVisible =
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth);

        if (!isVisible) return;

        switch (e.key) {
            case ' ':  // Space key play/pause
                if (video.paused) {
                    video.play();
                    playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                    videoWrapper.classList.remove('awaiting-interaction');
                } else {
                    video.pause();
                    playBtn.innerHTML = '<i class="fas fa-play"></i>';
                }
                e.preventDefault();
                break;
            case 'f':  // F key for fullscreen
                fullscreenBtn.click();
                e.preventDefault();
                break;
            case 'm':  // M key for mute
                video.muted = !video.muted;
                if (video.muted) {
                    muteBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
                } else {
                    muteBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
                }
                e.preventDefault();
                break;
        }
    });

    // Respond to window size changes, update video size
    window.addEventListener('resize', updateVideoSize);

    // Click progress bar to jump to position in video
    if (progressContainer) {
        progressContainer.addEventListener('click', function (e) {
            const rect = progressContainer.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            const seekTime = video.duration * pos;

            // Ensure time is valid
            if (isFinite(seekTime) && seekTime >= 0 && seekTime <= video.duration) {
                // Set new time
                video.currentTime = seekTime;

                // Directly update progress bar position, no need to wait for timeupdate
                lastProgress = pos * 100;
                progressBar.style.width = `${lastProgress}%`;

                // If video is paused, start playing
                if (video.paused) {
                    video.play().then(() => {
                        playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                        videoWrapper.classList.remove('awaiting-interaction');
                    }).catch(e => {
                        console.log('Playback failed:', e);
                    });
                }
            }
        });
    }
}

// Remove complex fullscreen exit handling function, simplify logic
function handleFullscreenExit() {
    // This function no longer needs complex logic, can be kept empty for future expansion
}

// Determine if page is being reloaded
function isPageReload() {
    // If page performance data is available, check navigation type
    if (window.performance && window.performance.navigation) {
        return window.performance.navigation.type === 1; // 1 indicates page refresh
    }

    // For newer browsers, use Navigation Timing API
    if (window.performance && window.performance.getEntriesByType && window.performance.getEntriesByType('navigation').length) {
        return window.performance.getEntriesByType('navigation')[0].type === 'reload';
    }

    // If unable to determine, assume not a refresh
    return false;
}

// Matrix effect
function initMatrixEffect() {
    const canvas = document.getElementById('matrix-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Set canvas size to window size
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Get style variables
    const computedStyle = getComputedStyle(document.documentElement);
    const primaryColor = computedStyle.getPropertyValue('--primary-color').trim() || '#00ffcc';
    const secondaryColor = computedStyle.getPropertyValue('--secondary-color').trim() || '#0088ff';

    // Matrix characters
    const chars = "01010101";
    const fontSize = 12;
    const columns = Math.floor(canvas.width / fontSize);

    // Current position for each column
    const drops = [];
    for (let i = 0; i < columns; i++) {
        drops[i] = Math.random() * -100;
    }

    // Define draw function
    function draw() {
        // Semi-transparent black background, creates trail effect
        ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Set text style
        ctx.font = `${fontSize}px monospace`;

        // Draw characters
        for (let i = 0; i < columns; i++) {
            // Randomly select character
            const char = chars[Math.floor(Math.random() * chars.length)];

            // Set gradient color based on position
            const y = drops[i] * fontSize;
            const gradient = ctx.createLinearGradient(0, y - fontSize, 0, y);
            gradient.addColorStop(0, primaryColor);
            gradient.addColorStop(1, secondaryColor);

            // Set fill style
            ctx.fillStyle = gradient;
            if (Math.random() > 0.99) {
                ctx.fillStyle = '#ffffff';
            }

            // Draw character
            ctx.fillText(char, i * fontSize, y);

            // Reset after reaching bottom, or randomly reset
            if (y > canvas.height && Math.random() > 0.99) {
                drops[i] = 0;
            }

            // Update position
            drops[i]++;
        }

        // Implement animation using requestAnimationFrame
        requestAnimationFrame(draw);
    }

    // Start animation
    draw();
}

// Dynamic ripple effect
function initRippleEffect() {
    const techCircles = document.querySelectorAll('.tech-circle');

    // If no tech-circle elements exist, don't execute
    if (!techCircles.length) return;

    // Dynamically adjust circle positions
    function updateCirclePositions() {
        techCircles.forEach((circle, index) => {
            // Slightly adjust circles based on mouse position
            document.addEventListener('mousemove', (e) => {
                const { clientX, clientY } = e;
                const centerX = window.innerWidth / 2;
                const centerY = window.innerHeight / 2;

                // Calculate distance between mouse and center
                const offsetX = (clientX - centerX) / centerX * 10;
                const offsetY = (clientY - centerY) / centerY * 10;

                // Set position offset, different for each circle
                const factor = 1 - index * 0.2;
                circle.style.transform = `translate(calc(-50% + ${offsetX * factor}px), calc(-50% + ${offsetY * factor}px)) scale(var(--scale))`;
            });
        });
    }

    // Only enable on desktop for performance reasons
    if (window.innerWidth > 1024) {
        updateCirclePositions();
    }
}

// Dynamic grid effect
function initGridEffect() {
    const gridOverlay = document.querySelector('.grid-overlay');
    if (!gridOverlay) return;

    let isAnimating = false;

    // Add mouse movement interaction
    document.addEventListener('mousemove', (e) => {
        if (isAnimating) return;

        // Slightly tilt grid based on mouse position
        const { clientX, clientY } = e;
        const rotateX = (clientY / window.innerHeight - 0.5) * 3;
        const rotateY = (clientX / window.innerWidth - 0.5) * -3;

        gridOverlay.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    // Add interactive click effect
    document.addEventListener('click', () => {
        if (isAnimating) return;
        isAnimating = true;

        // Add pulse effect on click
        gridOverlay.style.animation = 'none';
        gridOverlay.offsetHeight; // Trigger reflow
        gridOverlay.style.animation = 'grid-pulse 1s forwards';

        setTimeout(() => {
            gridOverlay.style.animation = 'grid-fade 8s infinite alternate';
            isAnimating = false;
        }, 1000);
    });

    // Add pulse effect keyframes
    const style = document.createElement('style');
    style.textContent = `
        @keyframes grid-pulse {
            0% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.01); }
            100% { opacity: 0.5; transform: scale(1); }
        }
    `;
    document.head.appendChild(style);
}

// Generate colored stars
function initStars() {
    const starsContainer = document.querySelector('.stars-container');
    if (!starsContainer) return;

    // Clear existing content
    starsContainer.innerHTML = '';

    // Define star colors
    const colors = [
        '#00ffcc', // Cyan
        '#0088ff', // Blue
        '#aa00ff', // Purple
        '#ff00aa', // Pink
        '#ffcc00', // Yellow
        '#ff3366', // Red
        '#33ffaa'  // Light green
    ];

    // Create random stars
    const starCount = Math.min(window.innerWidth / 3, 150); // Adaptive star count based on screen width

    for (let i = 0; i < starCount; i++) {
        const star = document.createElement('div');
        star.className = 'star';

        // Random position
        star.style.left = `${Math.random() * 100}%`;
        star.style.top = `${Math.random() * 100}%`;

        // Random size (1-3px)
        const size = Math.random() * 2 + 1;
        star.style.width = `${size}px`;
        star.style.height = `${size}px`;

        // Random color
        const color = colors[Math.floor(Math.random() * colors.length)];
        star.style.setProperty('--color', color);

        // Random glow size
        const glowSize = Math.random() * 6 + 2;
        star.style.setProperty('--glow-size', `${glowSize}px`);

        // Random animation duration (2-8 seconds)
        const duration = Math.random() * 6 + 2;
        star.style.setProperty('--duration', `${duration}s`);

        // Random animation delay
        const delay = Math.random() * 5;
        star.style.setProperty('--delay', `${delay}s`);

        // Random opacity
        const opacity = Math.random() * 0.5 + 0.4;
        star.style.setProperty('--opacity', opacity);

        // Add to container
        starsContainer.appendChild(star);
    }

    // Add some large, bright stars
    for (let i = 0; i < 15; i++) {
        const star = document.createElement('div');
        star.className = 'star';

        // Random position
        star.style.left = `${Math.random() * 100}%`;
        star.style.top = `${Math.random() * 100}%`;

        // Larger size
        const size = Math.random() * 2 + 2;
        star.style.width = `${size}px`;
        star.style.height = `${size}px`;

        // Random color
        const color = colors[Math.floor(Math.random() * colors.length)];
        star.style.setProperty('--color', color);

        // Larger glow effect
        const glowSize = Math.random() * 10 + 5;
        star.style.setProperty('--glow-size', `${glowSize}px`);

        // Longer animation duration
        const duration = Math.random() * 8 + 4;
        star.style.setProperty('--duration', `${duration}s`);

        // Random animation delay
        const delay = Math.random() * 5;
        star.style.setProperty('--delay', `${delay}s`);

        // Higher opacity
        star.style.setProperty('--opacity', '0.8');

        // Add to container
        starsContainer.appendChild(star);
    }
}

// Initialize all background effects
function initBackgroundEffects() {
    initMatrixEffect();
    initRippleEffect();
    initGridEffect();
    initStars();

    // Regenerate stars when window size changes
    window.addEventListener('resize', () => {
        // Throttle handling to avoid frequent calls
        if (window.starResizeTimeout) {
            clearTimeout(window.starResizeTimeout);
        }
        window.starResizeTimeout = setTimeout(() => {
            initStars();
        }, 500);
    });
}

// Initialize all effects when page load completes
document.addEventListener('DOMContentLoaded', function () {
    // Initialize loading screen
    initLoadingScreen();

    // Initialize particle effect
    createRandomParticle();

    // Initialize theme option animations
    animateThemeOptions();

    // Initialize video player
    initVideoPlayer();

    // Initialize background effects
    initBackgroundEffects();
});

// For development environment only - clear session state
function resetVisitState() {
    // Clear session state related variables
    sessionStorage.clear();
    console.log('Visit state has been reset. This will simulate a first-time visit on the next navigation.');
}

// Comment out the line below to disable automatic reset (for development use only)
// resetVisitState();
