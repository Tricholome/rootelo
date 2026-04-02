// Moteur de Scroll Dynamique pour le CSS
window.addEventListener('scroll', () => {
	const scrollY = window.scrollY;
	const isMobile = window.innerWidth < 1100;

	// 1. Toujours mettre à jour la variable pour le calcul PC (max 50%...)
	document.body.style.setProperty('--scroll', scrollY);

	// 2. Logique HAUT (Bannière)
	if (scrollY > 30) {
		document.body.classList.add('is-scrolled');
	} else {
		document.body.classList.remove('is-scrolled');
	}

	// 3. Logique BAS (Uniquement Mobile pour éviter les bugs PC)
	if (isMobile) {
		const windowHeight = window.innerHeight;
		const docHeight = document.documentElement.scrollHeight;
		// Déclenche à 50px du bord fial
		if ((windowHeight + scrollY) >= (docHeight - 50)) {
			document.body.classList.add('is-at-bottom');
		} else {
			document.body.classList.remove('is-at-bottom');
		}
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
			desc: 'The absolute pinnacle of the Woodland. Reaching this height is a rare feat, a fleeting and prestigious throne where staying at the top is a constant battle against gravity. It is reserved for those who maintain perfection under pressure.'
		},
		'fox': {
			name: 'Fox',
			elo: '1400+',
			subtitle: 'The Cunning Tacticians',
			desc: 'The sharpest minds on the ladder, thriving on wit over brute force. The hunt presses close from all sides, where a single hesitation proves fatal. Escaping through a signature trick, every step is measured with care, every slip is exploited with flair.'
		},
		'rabbit': {
			name: 'Rabbit',
			elo: '1300+',
			subtitle: 'The Agile Contenders',
			desc: 'The true engine of the higher rankings. Their climb is built on speed and sharp adaptability, moving well past the basics to dictate the pace of play. They are restless challengers, always seeking the next opening to leap ahead.'
		},
		'mouse': {
			name: 'Mouse',
			elo: '1200+',
			subtitle: 'The Steady Foragers',
			desc: 'The solid foundation of the standings, marking a genuine milestone beyond the average player. These resilient competitors provide the first true test on the ladder, proving they have the consistency required to begin a successful climb. They are where every journey starts.'
		},
		'squirrel': {
			name: 'Squirrel',
			elo: '< 1200',
			subtitle: 'The Hapless Stragglers',
			desc: 'The frantic collectors of the undergrowth. Often tripped up by clumsy errors or bad luck, they must fall back to let faster rivals pass. Yet, they remain busy; every scrap gathered today is a seed stored away for next season’s harvest.'
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
