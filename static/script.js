// Dynamic Scroll & Gesture Management
let touchStartY = 0;
let touchEndY = 0;

window.addEventListener('touchstart', (e) => {
    touchStartY = e.changedTouches[0].pageY;
}, { passive: true });

window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    document.body.style.setProperty('--scroll', scrollY);

    if (scrollY > 30) {
        document.body.classList.add('is-scrolled');
    } else {
        document.body.classList.remove('is-scrolled');
    }
}, { passive: true });

window.addEventListener('touchend', (e) => {
    const isMobile = window.innerWidth < 1100;
    if (!isMobile) return;

    touchEndY = e.changedTouches[0].pageY;
    
    const windowHeight = window.innerHeight;
    const docHeight = document.documentElement.scrollHeight;
    const isAtBottomPos = (Math.ceil(windowHeight + window.scrollY) >= docHeight - 20);
    const hasClass = document.body.classList.contains('is-at-bottom');

    // Distance traveled by the finger
    const swipeDistance = touchStartY - touchEndY;

    /**
     * TRIGGER: If we were at the bottom and swiped UP significantly
     */
    if (isAtBottomPos && !hasClass && swipeDistance > 70) {
        document.body.classList.add('is-at-bottom');
        // Optional: force scroll to top or lock body if needed
    }

    /**
     * RESET: If the image is out and we swipe DOWN
     * We use a negative distance (touchStartY < touchEndY)
     */
    if (hasClass && swipeDistance < -50) {
        document.body.classList.remove('is-at-bottom');
    }
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
