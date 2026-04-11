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

// Double-tap
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

// Nut surprise
document.addEventListener('DOMContentLoaded', () => {
	
	// --- BLOC 1 : Feature "Nut" ---
    if (window.location.hash === '#nut-section') {
        const nutSection = document.getElementById('nut-section');
        if (nutSection) {
            nutSection.style.display = 'block';
        }
    }
	
	// --- BLOC 2 : Feature "Deco" ---
    const btn = document.getElementById('deco-toggle');
    if (btn) {
        btn.addEventListener('click', () => {
            // On ajoute ou on enlève la classe "show-deco" au body
            document.body.classList.toggle('show-deco');
			
			setTimeout(() => {
                window.dispatchEvent(new Event('scroll'));
            }, 600);
        });
    }
	
});

/* =========================================================
   GESTION DU SECRET ET RIDEAU NOIR 
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {

    const secretSequence = ['roots', 'quiet'];
    let userProgress = [];

    // --- Fonction pour changer les textes ---
   const updateTexts = () => {
		if (document.body.getAttribute('data-page') === 'cache') {
			const intro = document.querySelector('.page-intro');
			if (intro) {
				const titleEl = intro.querySelector('h2');
				const descEl = intro.querySelector('p');
				if (titleEl) titleEl.textContent = "Mystic Sward";
				if (descEl) descEl.textContent = "Silent roots keep a quiet crown.";
			}
			document.title = "Mystic Sward • Rootelo";
		}

		const nav = document.querySelector('nav');
		if (nav && !document.getElementById('nav-mystic')) {
			const mysticLink = document.createElement('a');
			mysticLink.id = 'nav-mystic';
			mysticLink.href = 'cache.html'; 
			mysticLink.textContent = 'Mystic Sward';
			
			if (document.body.getAttribute('data-page') === 'cache') {
				mysticLink.className = 'active';
				const links = nav.querySelectorAll('a');
				links.forEach(a => {
					if (a.textContent === 'Undergrowth') a.style.display = 'none';
				});
			}

			nav.appendChild(mysticLink);
		}
	};

    // On écoute les clics sur les mots "cipher"
    document.querySelectorAll('.cipher').forEach(el => {
        el.addEventListener('click', () => {
            const word = el.getAttribute('data-word');
            
            if (word === secretSequence[userProgress.length]) {
                userProgress.push(word);
                el.classList.add('active-cipher');

                if (userProgress.length === secretSequence.length) {
                    const gate = document.getElementById('mystic-gate');
                    
                    $(gate).fadeIn(600, function() {
                        document.body.classList.add('mystic');
                        document.body.classList.add('show-deco');
                        localStorage.setItem('mysticUnlocked', 'true');
                        
                        // ON CHANGE LES TEXTES ICI
                        updateTexts();
                        
                        if (typeof initStardust === "function") initStardust();

                        $(gate).fadeOut(1000);
                    });
                }
            } else {
                userProgress = [];
                document.querySelectorAll('.cipher').forEach(c => c.classList.remove('active-cipher'));
            }
        });
    });

    // FULL RESET
	const exitBtn = document.getElementById('leave-secrets');

	if (exitBtn) {
		exitBtn.addEventListener('click', () => {
			localStorage.clear();
			window.location.href = 'index.html';
		});
	}

    // PERSISTANCE
    if (localStorage.getItem('mysticUnlocked') === 'true') {
        document.body.classList.add('mystic');
        document.body.classList.add('show-deco');
        
        // ON CHANGE LES TEXTES ICI AUSSI
        updateTexts();
        
        if (typeof initStardust === "function") initStardust();
    }
});

/* =========================================================
   GÉNÉRATEUR DE POUSSIÈRE D'ÉTOILES
   ========================================================= */

function initStardust() {
    $('.window-box').each(function() {
        const box = $(this);
        
        // Ajout du conteneur s'il n'existe pas
        if (box.find('.stardust-container').length === 0) {
            box.prepend('<div class="stardust-container"></div>');
        }
        
        const container = box.find('.stardust-container');
        const boxHeight = box.innerHeight();
        
        // Densité d'étoiles basée sur la taille de la boîte
        const starCount = Math.floor(boxHeight / 30); 

        for (let i = 0; i < starCount; i++) {
            const size = (Math.random() * 2 + 1) + 'px';
            const star = $('<div class="star"></div>').css({
                width: size,
                height: size,
                left: Math.random() * 100 + '%',
                top: Math.random() * 100 + '%',
                '--duration': (Math.random() * 3 + 2) + 's',
                'animation-delay': (Math.random() * 5) + 's'
            });
            container.append(star);
        }
    });
}
