/* =========================================================================
   ROOTELO - JAVASCRIPT
   Table of Contents:
   1. Dynamic Scroll
   2. Double-tap
   3. Tier Modal
   4. Secrets Engine
   5. Nut & Berry
   6. Stardust Generator

   ========================================================================= */
   
/* =========================================================================
   --- 1. DYNAMIC SCROLL ---
   ========================================================================= */

// Dynamic Scroll & Gesture Management
// Variables to track touch positions and scroll direction
let touchStartY = 0;
let lastScrollY = window.scrollY;

// 1. Capture the initial touch position on the physical screen (clientY)
// Using clientY instead of pageY makes it immune to overscroll/bounce effects
window.addEventListener('touchstart', (e) => {
    touchStartY = e.touches[0].clientY; 
}, { passive: true });

// 2. Handle specific swipe gestures for the bottom image reveal
window.addEventListener('touchmove', (e) => {
    const isMobile = window.innerWidth < 1100;
    if (!isMobile) return;

    const currentY = e.touches[0].clientY;
    const hasClass = document.body.classList.contains('is-at-bottom');

    if (hasClass && (currentY - touchStartY) > 40) {
        document.body.classList.remove('is-at-bottom');
        return; // Exit early
    }

    const windowHeight = window.innerHeight;
    const docHeight = document.documentElement.scrollHeight;
    // 15px margin to ensure it triggers even with minor calculation rounding
    const isAtBottom = Math.ceil(windowHeight + window.scrollY) >= (docHeight - 15);

    // If at the bottom AND swiping UP intentionally (finger moves up by more than 70px)
    if (isAtBottom && !hasClass && (touchStartY - currentY) > 70) {
        document.body.classList.add('is-at-bottom');
    }
}, { passive: true });

// 3. Handle standard scrolling (Header logic + Fallback reset)
window.addEventListener('scroll', () => {
    const currentScrollY = window.scrollY;
    const isMobile = window.innerWidth < 1100;

    // Set CSS variable for dynamic scroll effects
    document.body.style.setProperty('--scroll', currentScrollY);

    // Header logic: toggle class when scrolling past 30px
    if (currentScrollY > 30) {
        document.body.classList.add('is-scrolled');
    } else {
        document.body.classList.remove('is-scrolled');
    }

    if (isMobile && document.body.classList.contains('is-at-bottom')) {
        // If the current scroll position is higher than the previous one (scrolling up)
        if (currentScrollY < lastScrollY - 10) {
            document.body.classList.remove('is-at-bottom');
        }
    }
    
    // Update last scroll position for the next event check
    lastScrollY = currentScrollY;
}, { passive: true });

/* =========================================================================
   --- 2. DOUBLE-TAP ---
   ========================================================================= */
   
document.addEventListener("DOMContentLoaded", function() {
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || (window.matchMedia("(hover: none)").matches);

    if (isTouchDevice) {
        // On écoute sur le body pour capter même les icônes créées par DataTables
        document.body.addEventListener('click', function(e) {
            // On cherche si on a cliqué sur un lien double-tap
            const link = e.target.closest('.js-double-tap');

            // 1. Si on clique ailleurs : on ferme tout
            if (!link) {
                document.querySelectorAll('.js-double-tap.expanded').forEach(l => l.classList.remove('expanded'));
                return;
            }

            // 2. Si on clique sur une icône
            if (!link.classList.contains('expanded')) {
                // PREMIER TAP
                e.preventDefault();
                e.stopPropagation();

                // On ferme les autres
                document.querySelectorAll('.js-double-tap.expanded').forEach(l => l.classList.remove('expanded'));
                
                // On ouvre celle-ci
                link.classList.add('expanded');
            } else {
                // DEUXIÈME TAP
                // On laisse le comportement naturel (onclick du HTML ou href)
                link.classList.remove('expanded');
            }
        }, true); // Le "true" ici permet d'intercepter avant DataTables
    }
});

/* =========================================================================
   --- 3. TIER MODAL ---
   ========================================================================= */
		
// Tier Modal		
document.addEventListener('DOMContentLoaded', function() {
	const modal = document.getElementById('tierModal');
	const modalBody = document.getElementById('modalBody');
	const closeBtn = document.querySelector('.modal-close');

	// Dictionnaire des textes exacts (About)
	const tierTexts = {
		'bird': {
			name: 'Bird',
			elo: '1500+',
			subtitle: 'The Grandmasters',
			desc: 'These elite sovereigns sit at the absolute pinnacle of the Woodland canopy. Remaining on this prestigious throne is a dizzying battle against shifting winds and ambitious rivals. They rule the skies by maintaining flawless execution and absolute perfection under pressure.'
		},
		'fox': {
			name: 'Fox',
			elo: '1400+',
			subtitle: 'The Cunning Tacticians',
			desc: 'These keen strategists dominate the ladder by thriving on sharp wit over brute force. The hunt presses close from all sides, and a single moment of hesitation can prove fatal. They prevail by measuring every step with care and exploiting weakness with signature flair.'
		},
		'rabbit': {
			name: 'Rabbit',
			elo: '1300+',
			subtitle: 'The Agile Contenders',
			desc: 'These nimble wanderers gracefully weave through the crowded and shifting paths of the rankings. Routine strategies falter here, threatening to trap anyone who cannot adapt to sudden chaos. They leap ahead where others see only barriers, turning dead ends into daring escapes.'
		},
		'mouse': {
			name: 'Mouse',
			elo: '1200+',
			subtitle: 'The Steady Foragers',
			desc: 'These resilient souls rise above the casual fray to mark a true milestone of mastery. The wild now demands true stamina, where early momentum easily fades into exhaustion. They hold their ground through quiet consistency, proving that steady patience outlasts blind luck.'
		},
		'squirrel': {
			name: 'Squirrel',
			elo: '< 1200',
			subtitle: 'The Hapless Stragglers',
			desc: 'These frantic collectors dwell in the tangled undergrowth of the ranking system. Clumsy errors and brutal defeats often force them to fall back while fiercer beasts surge ahead. Yet, they bravely endure by turning every painful lesson into a seed for next season’s harvest.'
		},
		'stag': {
			name: 'Stag',
			elo: '1600+',
			subtitle: 'The Legend',
			desc: 'To be defined.'
		}
	};

	// On récupère les couleurs et icônes depuis l'objet CONFIG créé dans le HTML
		const tierColors = CONFIG.colors;
		const tierIcons = CONFIG.icons;

	window.openTierModal = function(tier) {
		const text = tierTexts[tier];
		const color = tierColors[tier] || tierColors['default'];
		const icon = tierIcons[tier];

		if (!text) return;

		const modalContent = modal.querySelector('.modal-content');
    	modalContent.style.setProperty('--tier-color', color);

		// On cible les éléments déjà existants dans le HTML
		const modalTitle = document.getElementById('modalTitle');
		const modalElo = document.getElementById('modalElo');
		const modalIcon = document.getElementById('modalIcon');
		const modalSubtitle = document.getElementById('modalSubtitle');
		const modalText = document.getElementById('modalText');

		modalTitle.textContent = text.name;
		
		modalElo.textContent = text.elo;
		modalElo.style.color = color;
		
		modalIcon.src = icon;
		
		modalSubtitle.textContent = text.subtitle;
		
		modalText.textContent = text.desc;

		modal.style.display = 'flex';
		document.body.style.overflow = 'hidden';
	};

	const closeModal = () => {
		modal.style.display = 'none';
		document.body.style.overflow = 'auto';
	};

	if (closeBtn) closeBtn.onclick = closeModal;
	window.onclick = (event) => { if (event.target == modal) closeModal(); };
});


/* =========================================================================
   --- 4. SECRETS ENGINE ---
   ========================================================================= */

document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
	
	// --- 0. FINAL COMPLETION ---
	function checkFinalCompletion() {
		const required = ['watcher-found', 'nut-found', 'berry-found', 'ciphers-found'];
		const allFound = required.every(key => localStorage.getItem(key) === 'true');

		if (allFound) {
			document.body.classList.add('secrets-ended');
			localStorage.setItem('secrets-ended', 'true');
		}
	}

    // --- 1. PERSISTENCE CHECK ---
	const isEnded = localStorage.getItem('secrets-ended') === 'true';
    const isWatcherFound = localStorage.getItem('watcher-found') === 'true';
    const isNutFound = localStorage.getItem('nut-found') === 'true';
	const isBerryFound = localStorage.getItem('berry-found') === 'true';
    const isCiphersFound = localStorage.getItem('ciphers-found') === 'true';
	const isHofUnlocked = localStorage.getItem('hof-unlocked') === 'true';

    // Global visibility (Nav & Exit)
    if (isWatcherFound || isNutFound || isBerryFound || isCiphersFound) {
        body.classList.add('secrets-started');
    }

    // Specific states
    if (isWatcherFound) body.classList.add('watcher-found');
    if (isNutFound) body.classList.add('nut-found');
	if (isBerryFound) body.classList.add('berry-found');
	if (isCiphersFound) {
        body.classList.add('ciphers-found');
        updateMysticUI();
    }
    
    // Final state
    if (isEnded) body.classList.add('secrets-ended');
	if (isHofUnlocked) {
		body.classList.add('hof-unlocked');
		if (typeof initStardust === "function") initStardust();
	}

    // --- 2. UI TRANSFORMATION FUNCTION ---
    function updateMysticUI() {
        if (body.getAttribute('data-page') === 'cache') {
            const intro = document.querySelector('.page-intro');
            if (intro) {
                const titleEl = intro.querySelector('h2');
                const descEl = intro.querySelector('p');
                if (titleEl) titleEl.textContent = "Glade of Fame";
                if (descEl) descEl.textContent = "Silent roots remember every crown.";
            }
            document.title = "Glade of Fame • Rootelo";
        }

        const navSecretLink = document.querySelector('.nav-secret');
        if (navSecretLink) {
            navSecretLink.textContent = 'Glade of Fame';
        }
    }
	
	// --- 3. THE WATCHER SECRET ---
    const watcherBtn = document.getElementById('watcher-secret');
    if (watcherBtn) {
        watcherBtn.addEventListener('click', () => {
            body.classList.add('secrets-started', 'watcher-found');
            localStorage.setItem('secrets-started', 'true');
            localStorage.setItem('watcher-found', 'true');
			checkFinalCompletion();
            window.dispatchEvent(new Event('scroll'));
        });
    }

    // --- 4. THE NUT SECRET ---
    if (window.location.hash === '#nut-section') {
        const nutSection = document.getElementById('nut-section');
        if (nutSection) nutSection.style.display = 'block';
    }

    const nutBtn = document.getElementById('nut-secret');
    if (nutBtn) {
        nutBtn.addEventListener('click', () => {
            body.classList.add('secrets-started', 'nut-found');
            localStorage.setItem('secrets-started', 'true');
            localStorage.setItem('nut-found', 'true');
			checkFinalCompletion();
        });
    }
	
	// --- 5. THE BERRY SECRET ---
    if (window.location.hash === '#berry-section') {
        const berrySection = document.getElementById('berry-section');
        if (berrySection) berrySection.style.display = 'block';
    }

    const berryBtn = document.getElementById('berry-secret');
    if (berryBtn) {
        berryBtn.addEventListener('click', () => {
            body.classList.add('secrets-started', 'berry-found');
            localStorage.setItem('secrets-started', 'true');
            localStorage.setItem('berry-found', 'true');
			checkFinalCompletion();
        });
    }

    // --- 6. THE CIPHER SEQUENCE & CURTAIN ---
    const secretSequence = ['silent', 'roots', 'remember', 'every', 'crown'];
    let userProgress = [];
    let isResetting = false;

    document.querySelectorAll('.cipher').forEach(el => {
        el.addEventListener('click', () => {
            // Check if already solved or currently resetting
            const isAlreadySolved = body.classList.contains('ciphers-found');
            if (isAlreadySolved || isResetting) return;

            el.classList.add('active-cipher');
            const word = el.getAttribute('data-word');
            
            if (word === secretSequence[userProgress.length]) {
                // Correct step
                userProgress.push(word);

                if (userProgress.length === secretSequence.length) {
                    const gate = document.getElementById('mystic-gate');
                    
                    $(gate).fadeIn(600, function() {
                        body.classList.add('ciphers-found');
                        localStorage.setItem('ciphers-found', 'true');
                        updateMysticUI();
						checkFinalCompletion();

                        $(gate).fadeOut(1000);
                    });
                }
            } else {
                setTimeout(() => {
					document.querySelectorAll('.cipher').forEach(c => {
						if (c.classList.contains('active-cipher')) c.classList.add('cipher-blink');
					});
					
					setTimeout(() => {
						userProgress = [];
						document.querySelectorAll('.cipher').forEach(c => {
							c.classList.remove('active-cipher', 'cipher-blink');
						});
					}, 500);
				}, 3000);
            }
        });
    });
	
	// --- 6. HALL OF FAME FINAL UNLOCK ---
	const hofBtn = document.getElementById('hof-access');
	if (hofBtn) {
		hofBtn.addEventListener('click', () => {
			const isEnded = localStorage.getItem('secrets-ended') === 'true';
			if (!isEnded) return;

			body.classList.add('hof-unlocked');
			localStorage.setItem('hof-unlocked', 'true');
			$('#leaderboard').DataTable().responsive.recalc();
			if (typeof initStardust === "function") initStardust();
		});
	}

	// --- 7. THE EXIT DOOR ---
	function handleExit(e) {
		const btn = e.currentTarget;
		const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

		if (isTouch && !btn.classList.contains('expanded')) {
			return;
		}

		e.preventDefault();

		localStorage.clear();
		document.body.classList.remove(
			'is-at-bottom', 'is-scrolled', 'secrets-started', 
			'watcher-found', 'nut-found', 'berry-found', 
			'ciphers-found', 'secrets-ended', 'hof-unlocked'
		);

		window.location.href = btn.getAttribute('href');
	}

});

/* =========================================================================
   --- 5. NUT & BERRY ---
   ========================================================================= */

function handleTierClick(event, tier) {
    const isNutFound = localStorage.getItem('nut-found') === 'true';
    const isBerryFound = localStorage.getItem('berry-found') === 'true';

    if (tier === 'squirrel' && !isNutFound) {
        window.location.href = 'cache.html#nut-section';
    } 
    else if (tier === 'stag' && !isBerryFound) {
        window.location.href = 'cache.html#berry-section';
    } 
    else {
        if (typeof openTierModal === "function") {
            openTierModal(tier);
        }
    }
}

/* =========================================================================
   --- 6. STARDUST GENERATOR ---
   ========================================================================= */

function initStardust() {
    $('.window-box').each(function() {
        const box = $(this);
        
        // Ensure only one container exists per box
        if (box.find('.stardust-container').length === 0) {
            box.prepend('<div class="stardust-container"></div>');
        }
        
        const container = box.find('.stardust-container');
        const boxHeight = box.innerHeight();
        
        // Star density based on box height
        const starCount = Math.floor(boxHeight / 30); 

        for (let i = 0; i < starCount; i++) {
            const size = (Math.random() * 2 + 1) + 'px';
            const star = $('<div class="star"></div>').css({
                'width': size,
                'height': size,
                'left': Math.random() * 100 + '%',
                'top': Math.random() * 100 + '%',
                '--duration': (Math.random() * 3 + 2) + 's',
                'animation-delay': (Math.random() * 5) + 's'
            });
            container.append(star);
        }
    });
}
