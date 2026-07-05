// ========== static/theme.js ==========
// HỆ THỐNG NỀN SAO VÀ CHẾ ĐỘ TỐI/SÁNG DÙNG CHUNG CHO TẤT CẢ TRANG

let starAnimationId = null;
let starCtx = null;
let starCanvas = null;
let starsArray = [];
let meteorsArray = [];
let isStarSystemActive = false;

function initStarfieldPro() {
    starCanvas = document.getElementById('star-canvas-background');
    if (!starCanvas) return;
    starCtx = starCanvas.getContext('2d');
    
    function resizeCanvasPro() {
        starCanvas.width = window.innerWidth;
        starCanvas.height = window.innerHeight;
        initStarsPro();
    }
    
    function initStarsPro() {
        starsArray = [];
        for (let i = 0; i < 1500; i++) {
            starsArray.push({
                x: Math.random() * starCanvas.width,
                y: Math.random() * starCanvas.height,
                r: Math.random() * 0.8,
                alpha: Math.random() * 0.5 + 0.5,
                speed: Math.random() * 0.3
            });
        }
    }
    
    function createMeteorPro() {
        meteorsArray.push({
            x: Math.random() * starCanvas.width,
            y: Math.random() * starCanvas.height / 2,
            len: Math.random() * 300 + 100,
            speed: Math.random() * 8 + 4,
            alpha: 1
        });
    }
    
    function drawStarsPro() {
        if (!starCtx || !starCanvas) return;
        starCtx.clearRect(0, 0, starCanvas.width, starCanvas.height);
        
        // Vẽ sao
        for (let s of starsArray) {
            starCtx.beginPath();
            starCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            starCtx.fillStyle = "rgba(255,255,255," + s.alpha + ")";
            starCtx.fill();
            s.alpha += (Math.random() - 0.5) * 0.05;
            s.alpha = Math.max(0, Math.min(1, s.alpha));
            s.y += s.speed;
            if (s.y > starCanvas.height) {
                s.y = 0;
                s.x = Math.random() * starCanvas.width;
            }
        }
        
        // Vẽ sao băng
        for (let i = meteorsArray.length - 1; i >= 0; i--) {
            let m = meteorsArray[i];
            let g = starCtx.createLinearGradient(m.x, m.y, m.x - m.len, m.y - m.len);
            g.addColorStop(0, "rgba(255,255,255,1)");
            g.addColorStop(1, "rgba(255,255,255,0)");
            starCtx.strokeStyle = g;
            starCtx.lineWidth = 2;
            starCtx.beginPath();
            starCtx.moveTo(m.x, m.y);
            starCtx.lineTo(m.x - m.len, m.y - m.len);
            starCtx.stroke();
            m.x += m.speed;
            m.y += m.speed;
            if (m.alpha <= 0) meteorsArray.splice(i, 1);
        }
        
        starAnimationId = requestAnimationFrame(drawStarsPro);
    }
    
    window.addEventListener('resize', () => {
        if (starCanvas && isStarSystemActive) {
            starCanvas.width = window.innerWidth;
            starCanvas.height = window.innerHeight;
            initStarsPro();
        }
    });
    
    setInterval(() => {
        if (isStarSystemActive) {
            let c = Math.floor(Math.random() * 2) + 3;
            for (let i = 0; i < c; i++) createMeteorPro();
        }
    }, 1500);
    
    initStarsPro();
    drawStarsPro();
}

let isDarkModeActive = false;

function toggleStarTheme() {
    const body = document.body;
    const starCanvasElem = document.getElementById('star-canvas-background');
    
    isDarkModeActive = !isDarkModeActive;
    
    if (isDarkModeActive) {
        body.classList.remove('light-mode');
        body.classList.add('dark-mode');
        
        if (starCanvasElem) {
            starCanvasElem.style.display = 'block';
            if (!starCtx) {
                isStarSystemActive = true;
                initStarfieldPro();
            } else {
                isStarSystemActive = true;
                if (!starAnimationId) {
                    function restartDraw() {
                        if (starCtx && starCanvas && isStarSystemActive) {
                            drawStarsPro();
                        }
                    }
                    restartDraw();
                }
            }
        }
    } else {
        body.classList.remove('dark-mode');
        body.classList.add('light-mode');
        
        if (starCanvasElem) {
            starCanvasElem.style.display = 'none';
        }
        isStarSystemActive = false;
        if (starAnimationId) {
            cancelAnimationFrame(starAnimationId);
            starAnimationId = null;
        }
    }
    
    localStorage.setItem('star_theme_mode', isDarkModeActive ? 'dark' : 'light');
    updateAllThemeIcons();
}

function updateAllThemeIcons() {
    const isDark = document.body.classList.contains('dark-mode');
    const themeIcons = document.querySelectorAll('#theme-icon, .theme-icon');
    const themeTexts = document.querySelectorAll('#theme-text, .theme-text');
    
    themeIcons.forEach(icon => {
        if (isDark) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
        }
    });
    
    themeTexts.forEach(text => {
        text.textContent = isDark ? 'Chế độ sáng' : 'Chế độ tối';
    });
}

function initTheme() {
    const savedTheme = localStorage.getItem('star_theme_mode');
    const body = document.body;
    const starCanvasElem = document.getElementById('star-canvas-background');
    
    if (savedTheme === 'dark') {
        body.classList.remove('light-mode');
        body.classList.add('dark-mode');
        if (starCanvasElem) {
            starCanvasElem.style.display = 'block';
            isStarSystemActive = true;
            initStarfieldPro();
        }
        isDarkModeActive = true;
    } else {
        body.classList.remove('dark-mode');
        body.classList.add('light-mode');
        if (starCanvasElem) {
            starCanvasElem.style.display = 'none';
        }
        isDarkModeActive = false;
    }
    
    updateAllThemeIcons();
}

// Tự động khởi tạo khi trang load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
} else {
    initTheme();
}

// Export ra global để có thể gọi từ onclick
window.toggleStarTheme = toggleStarTheme;