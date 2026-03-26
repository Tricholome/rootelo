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
			desc: 'The elite targets everyone is chasing. With a trick for every turn and a plan for every disaster, they outmaneuver the field with ease. They play with sharp instincts, punctuated by a signature, mischievous grin that keeps opponents guessing.'
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

		// On cible les éléments déjà existants dans le HTML
		const modalTitle = document.getElementById('modalTitle');
		const modalElo = document.getElementById('modalElo');
		const modalIcon = document.getElementById('modalIcon');
		const modalSubtitle = document.getElementById('modalSubtitle');
		const modalText = document.getElementById('modalText');

		modalTitle.textContent = text.name;
		
		modalElo.textContent = text.name;
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
		
// Fonction globale pour ouvrir la lightbox
function openLightbox(src) {
	const lb = document.getElementById('lightbox');
	const lbImg = document.getElementById('lightbox-img');
	lbImg.src = src;
	lb.style.display = 'flex';
}

// Fermeture avec la touche Echap
document.addEventListener('keydown', function(e) {
	if (e.key === "Escape") {
		const lb = document.getElementById('lightbox');
		if (lb) lb.style.display = 'none';
	}
});

document.addEventListener("DOMContentLoaded", function() {
	// Détection propre des appareils tactiles
	const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || (window.matchMedia("(hover: none)").matches);

	if (isTouchDevice) {
		document.querySelectorAll('.js-double-tap').forEach(link => {
			link.addEventListener('click', function(e) {
				// Si l'icône n'est pas encore "agrandie"
				if (!this.classList.contains('expanded')) {
					e.preventDefault(); // On bloque l'envoi vers l'ancre au premier clic
					
					// On referme toutes les autres icônes
					document.querySelectorAll('.js-double-tap').forEach(l => l.classList.remove('expanded'));
					
					// On agrandit celle-ci (ce qui lance le CSS et affiche le Tooltip)
					this.classList.add('expanded');
				}
				// Si l'élément a déjà la classe 'expanded', on ne fait rien, le lien <a> s'exécutera normalement.
			});
		});

		// Optionnel : Refermer les icônes si on tapote ailleurs sur l'écran
		document.addEventListener('click', function(e) {
			if (!e.target.closest('.js-double-tap')) {
				document.querySelectorAll('.js-double-tap').forEach(l => l.classList.remove('expanded'));
			}
		});
	}
});
