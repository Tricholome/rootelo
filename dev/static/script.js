/* =========================================================================
   ROOTELO - JAVASCRIPT
   Table of Contents:
   1. Dynamic Scroll
   2. Double-tap
   3. Tier Modal
   4. Data Tables
   5. Chart
   6. Secrets Engine
   7. Nut & Berry
   8. Visitor Recognition
   9. Dynamic Trends
   10. Narrative Journey

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
			desc: 'These elite sovereigns sit at the absolute pinnacle of the Woodland canopy. Remaining on this prestigious throne is a dizzying battle against shifting winds and ambitious rivals. They rule the skies by maintaining flawless execution and unerring control under pressure.'
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
			desc: 'These nimble wanderers gracefully weave through the crowded paths of the rankings. Routine strategies falter here, threatening to trap anyone who cannot adapt to sudden chaos. They leap ahead where others see only barriers, turning dead ends into daring escapes.'
		},
		'mouse': {
			name: 'Mouse',
			elo: '1200+',
			subtitle: 'The Steady Foragers',
			desc: 'These resilient souls rise above the casual fray to mark a milestone of mastery. The wild now demands pure stamina, where early momentum easily fades into exhaustion. They hold their ground through quiet consistency, proving that patience outlasts blind luck.'
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
			desc: 'Has anyone truly seen this mythical beast, or is it only an echo of the wild? What happens to the predator when the woods turn hollow and every path leads back to a mirror of its own perfection? With nothing left to be claimed, is the true crown the silence that follows the chase?'
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
		document.body.style.overflowY = 'auto';
		document.body.style.overflowX = 'hidden';
		if (window.innerWidth < 1100) {
			window.scrollTo(window.scrollX, window.scrollY);
		}
	};
	if (closeBtn) closeBtn.onclick = closeModal;

	window.onclick = (event) => { 
		if (event.target == modal) closeModal(); 
	};
});

/* =========================================================================
   --- 4. DATA TABLES ---
   ========================================================================= */

$(document).ready(function() {

    // --- 1. LEADERBOARD ---
    if ($('#leaderboard').length > 0) {
        // Sort "-" at the end
        $.extend($.fn.dataTable.ext.type.order, { 
            "rank-pre": function (d) { return d === "-" ? 9999 : parseInt(d); } 
        });

        $('#leaderboard').DataTable({
            "order": [[3, "desc"]],
            "responsive": true, 
            "pageLength": 50,
            "dom": '<"top"lf>rt<"bottom"ip><"clear">',
            "columnDefs": [ 
                { "targets": 0, "type": "rank" },
                { "targets": 2, "className": "player-name-cell" },
                { "targets": 3, "className": "elo-cell" },
				{ "className": "numeric-cell", "targets": [0, 3, 4, 5, 6, 7, 8] },
                { "responsivePriority": 1, "targets": [2, 3] },
                { "responsivePriority": 2, "targets": 0 },
                { "responsivePriority": 3, "targets": 1 },
                { "responsivePriority": 8, "targets": 6 },
                { "responsivePriority": 10, "targets": [4, 5, 7, 8] }
            ],
            "language": {
                "searchPlaceholder": "Player name"
            }
        });
    }
	
	// --- 2. MATCHES ---
    if ($('#matchesTable').length > 0) {
        $('#matchesTable').DataTable({
            "order": [[1, "desc"]], 
            "responsive": true,
            "pageLength": 50,
            "columnDefs": [
				{ "className": "rank-cell", "targets": 0 },
                { "className": "elo-sum-cell", "targets": 1 },
				{ "className": "date-cell", "targets": 2 },
				{ "className": "numeric-cell", "targets": [0, 1, 2, 4] },
                { "responsivePriority": 1, "targets": [1, 3] },
                { "responsivePriority": 2, "targets": [0, 2] },
                { "responsivePriority": 3, "targets": 4 }
            ],
            "language": {
                "searchPlaceholder": "Player name, Game ID..."
            }
        });
    }

    // --- 3. HALL OF FAME ---
	if ($('#hall_of_fame').length > 0) {
		$('#hall_of_fame').DataTable({
			"responsive": true,
			"ordering": false,
			"paging": false,
			"searching": false,
			"info": false,
			"dom": 'rt',
			"columnDefs": [
				{ "targets": 0, "className": "rank-cell" },
				{ "targets": 1, "className": "player-name-cell" },
				{ "targets": 2, "className": "streak-cell" },
				{ "targets": 3, "className": "elo-cell" },
				{ "targets": 4, "className": "date-cell" },
				{ "className": "numeric-cell", "targets": [2, 3, 4] },
				{ "responsivePriority": 1, "targets": [0, 1] },
				{ "responsivePriority": 2, "targets": [2, 3] },
				{ "responsivePriority": 3, "targets": 4 },
			]
		});
	}
	
	// --- 4. VISITOR TABLE ---
	if ($('#visitor_table').length > 0) {
		$('#visitor_table').DataTable({
			"responsive": true,
			"ordering": false,
			"paging": false,
			"searching": false,
			"info": false,
			"dom": 'rt',
			"columnDefs": [
				{ "targets": 0, "className": "rank-cell" },
			]
		});
	}
	
	// --- 5. GLOBAL FIX FOR ORIENTATION & RESIZE ---
    window.addEventListener('resize', () => {
        $('.dataTable').each(function() {
            if ($.fn.dataTable.isDataTable(this)) {
                $(this).DataTable()
                    .columns.adjust()
                    .responsive.recalc();
            }
        });
    });

});

/* =========================================================================
   --- 5. CHART (TRENDS) ---
   ========================================================================= */

let myChart;

function updateChart() {
    const input = document.getElementById('playerName');
    const canvas = document.getElementById('progressionChart');
    if (!input || !canvas) return;

    const name = input.value;
    const allData = CONFIG.chartData;

    if (name === "" || !allData[name]) {
        if (myChart) myChart.destroy();
        localStorage.removeItem('selectedPlayer');
        return;
    }

    const ctx = canvas.getContext('2d');
    const rabbitColor = getComputedStyle(document.documentElement).getPropertyValue('--color-rabbit').trim() || '#E0B634';
    
    if (typeof allData !== 'undefined' && allData[name]) {
        localStorage.setItem('selectedPlayer', name);

        const rawData = allData[name];
        const labels = rawData.map(d => {
            const dateObj = new Date(d[0]);
            return !isNaN(dateObj.getTime()) 
                ? dateObj.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) 
                : d[0];
        });
        const eloScores = rawData.map(d => d[1]);

        if (myChart) myChart.destroy();
        
        let lastClickTime = 0;
		let lastClickedIndex = -1;

		myChart = new Chart(ctx, {
			type: 'line',
			data: {
				labels: labels,
				datasets: [{
					data: eloScores,
					borderColor: rabbitColor,
					backgroundColor: rabbitColor + '22',
					borderWidth: 3,
					fill: true,
					tension: 0.3,
					pointRadius: 3,
					pointBackgroundColor: rabbitColor,
					pointHitRadius: 20
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				onClick: (e, elements) => {
					if (elements.length > 0) {
						const index = elements[0].index;
						const matchUrl = rawData[index][3];
						
						if (matchUrl) {
							if (e.native.pointerType === 'touch') {
								const currentTime = Date.now();
								const timeDiff = currentTime - lastClickTime;
								
								if (index === lastClickedIndex && timeDiff < 400) {
									window.open(matchUrl, '_blank');
									lastClickedIndex = -1;
								} else {
									lastClickedIndex = index;
								}
								lastClickTime = currentTime;
							} else {
								window.open(matchUrl, '_blank');
							}
						}
					}
				},
				onHover: (e, elements) => {
					e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
				},
				plugins: {
					legend: { display: false },
					tooltip: { 
						enabled: true, 
						backgroundColor: '#222', 
						titleColor: rabbitColor,
						callbacks: {
							footer: (tooltipItems) => {
								const index = tooltipItems[0].dataIndex;
								const matchUrl = rawData[index][3];
								
								if (matchUrl) {
									const isTouch = window.matchMedia('(pointer: coarse)').matches;
									return isTouch ? 'Double-tap for game details' : 'Click for game details';
								}
								return '';
							}
						},
						footerColor: '#aaa',
						footerFont: { size: 11, weight: 'normal' },
						footerSpacing: 4,
						marginSpacing: 6
					}
				},
				scales: {
					y: { grid: { color: '#252525' }, ticks: { color: '#888' } },
					x: { grid: { display: false }, ticks: { color: '#888', maxTicksLimit: 6 } }
				}
			}
		});
    }
}

$(document).ready(function() {
    if ($('#progressionChart').length > 0) {
        const input = document.getElementById('playerName');
        const savedPlayer = localStorage.getItem('selectedPlayer');

        if (savedPlayer && CONFIG.chartData[savedPlayer]) {
            input.value = savedPlayer;
            updateChart();
        }
        $(input).on('input', updateChart);
    }
});


/* =========================================================================
   --- 6. SECRETS ENGINE ---
   ========================================================================= */

document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
	
    // --- 0. FINAL COMPLETION ---
    function checkFinalCompletion() {
        const required = ['watcher-found', 'nut-found', 'berry-found', 'ciphers-found', 'warden-found'];
        const allFound = required.every(key => localStorage.getItem(key) === 'true');

        if (allFound) {
            body.classList.add('secrets-ended');
            localStorage.setItem('secrets-ended', 'true');
        }
    }
	
	// --- 1. MYSTIC TRANSITION ---
	function triggerMysticTransition(callback) {
		const gate = document.getElementById('mystic-gate');
		$(gate).fadeIn(600, function() {
			if (callback) callback();
			$(gate).fadeOut(1000);
		});
	}

    // --- 2. PERSISTENCE CHECK ---
    const isEnded = localStorage.getItem('secrets-ended') === 'true';
    const isWatcherFound = localStorage.getItem('watcher-found') === 'true';
    const isNutFound = localStorage.getItem('nut-found') === 'true';
    const isBerryFound = localStorage.getItem('berry-found') === 'true';
    const isCiphersFound = localStorage.getItem('ciphers-found') === 'true';
	const isWardenFound = localStorage.getItem('warden-found') === 'true';
    const isHofUnlocked = localStorage.getItem('hof-unlocked') === 'true';

    // Specific states
    if (isWatcherFound) body.classList.add('watcher-found');
    if (isNutFound) body.classList.add('nut-found');
    if (isBerryFound) body.classList.add('berry-found');
    if (isCiphersFound) {
        body.classList.add('ciphers-found');
        updateMysticUI();
    }
	if (isWardenFound) body.classList.add('warden-found');
    
    // Final state
    if (isEnded) body.classList.add('secrets-ended');
    if (isHofUnlocked) body.classList.add('hof-unlocked');

    // --- 3. UI TRANSFORMATION FUNCTION ---
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
	
    // --- 4. THE WATCHER SECRET ---
    const watcherBtn = document.getElementById('watcher-secret');
    if (watcherBtn) {
        watcherBtn.addEventListener('click', () => {
            body.classList.add('watcher-found');
            localStorage.setItem('watcher-found', 'true');
            checkFinalCompletion();
            window.dispatchEvent(new Event('scroll'));
        });
    }

    // --- 5. THE NUT SECRET ---
    if (window.location.hash === '#nut-section') {
        const nutSection = document.getElementById('nut-section');
        if (nutSection) nutSection.style.display = 'block';
    }

    const nutBtn = document.getElementById('nut-secret');
    if (nutBtn) {
        nutBtn.addEventListener('click', () => {
            body.classList.add('nut-found');
            localStorage.setItem('nut-found', 'true');
			nutBtn.removeAttribute('onclick');
            checkFinalCompletion();
        });
    }
	
    // --- 6. THE BERRY SECRET ---
    if (window.location.hash === '#berry-section') {
        const berrySection = document.getElementById('berry-section');
        if (berrySection) berrySection.style.display = 'block';
    }

    const berryBtn = document.getElementById('berry-secret');
    if (berryBtn) {
        berryBtn.addEventListener('click', () => {
            body.classList.add('berry-found');
            localStorage.setItem('berry-found', 'true');
			berryBtn.removeAttribute('onclick');
            checkFinalCompletion();
        });
    }

    // --- 7. THE CIPHER SEQUENCE ---
    const secretSequence = ['silent', 'roots', 'remember', 'every', 'crown'];
    let userProgress = [];
    let isResetting = false;

    document.querySelectorAll('.cipher').forEach(el => {
        el.addEventListener('click', () => {
            const isAlreadySolved = body.classList.contains('ciphers-found');
            
            if (isAlreadySolved || isResetting) return;

            el.classList.add('active-cipher');
            const word = el.getAttribute('data-word');
            
            if (word === secretSequence[userProgress.length]) {
                userProgress.push(word);

                if (userProgress.length === secretSequence.length) {
                    triggerMysticTransition(() => {
                        body.classList.add('ciphers-found');
                        localStorage.setItem('ciphers-found', 'true');
                        updateMysticUI();
                        checkFinalCompletion();
                    });
                }
            } else {
                isResetting = true; 

                setTimeout(() => {
                    document.querySelectorAll('.cipher').forEach(c => {
                        if (c.classList.contains('active-cipher')) c.classList.add('cipher-blink');
                    });
                    
                    setTimeout(() => {
                        userProgress = [];
                        document.querySelectorAll('.cipher').forEach(c => {
                            c.classList.remove('active-cipher', 'cipher-blink');
                        });
                        isResetting = false; 
                    }, 500);
                }, 800);
            }
        });
    });
	
	// --- 8. THE WARDEN SECRET ---
    const wardenBtn = document.getElementById('warden-secret');
    if (wardenBtn) {
        wardenBtn.addEventListener('click', () => {
            body.classList.add('warden-found');
            localStorage.setItem('warden-found', 'true');
            checkFinalCompletion();
            requestAnimationFrame(() => {
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            });
        });
    }
	
    // --- 9. HALL OF FAME FINAL UNLOCK ---
    const hofBtn = document.getElementById('hof-access');
	if (hofBtn) {
		hofBtn.addEventListener('click', () => {
			if (localStorage.getItem('secrets-ended') !== 'true') return;

			body.classList.add('hof-unlocked');
			localStorage.setItem('hof-unlocked', 'true');

			setTimeout(() => {
				if ($.fn.dataTable.isDataTable('#hall_of_fame')) {
					$('#hall_of_fame').DataTable()
						.columns.adjust()
						.responsive.recalc();
				}
			}, 50);
		});
	}

    // --- 10. THE EXIT DOOR ---
	const leaveBtn = document.querySelector('#leave-secrets');
	if (leaveBtn) {
		leaveBtn.addEventListener('click', (e) => {
			e.preventDefault(); 
			
			triggerMysticTransition(() => {
				localStorage.clear();
				document.body.className = ''; 
				window.location.href = 'index.html'; 
			});
		});
	}
});

/* =========================================================================
   --- 7. NUT & BERRY ---
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
   --- 8. VISITOR RECOGNITION ---
   ========================================================================= */

const btnEngrave = document.getElementById('btn-engrave');
const inputZone = document.getElementById('input-zone');
const btnConfirm = document.getElementById('btn-confirm');

window.addEventListener('DOMContentLoaded', () => {
    const savedName = localStorage.getItem('visitor_name');
    const savedDate = localStorage.getItem('discovery_date');
    if (savedName && savedDate) {
        showVisitorRow(savedName, savedDate);
    }
});

// 1. Bouton Engrave
if (btnEngrave && inputZone) {
    btnEngrave.addEventListener('click', () => {
        btnEngrave.style.display = 'none';
        inputZone.style.display = 'block';
    });
}

// 2. Confirmation
if (btnConfirm) {
    btnConfirm.addEventListener('click', () => {
        const nameInput = document.getElementById('visitor-name');
        const name = nameInput ? nameInput.value.trim() : ""; 

        if (name === "") return;

        const date = new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
        
        showVisitorRow(name, date);

        localStorage.setItem('visitor_name', name);
        localStorage.setItem('discovery_date', date);
    });
}

function showVisitorRow(name, date) {
    const visitorTable = document.getElementById('visitor_table');
    if (visitorTable) {
        visitorTable.querySelector('.visitor-name').textContent = name;
        visitorTable.querySelector('.visitor-date').textContent = date;
        visitorTable.style.setProperty('display', 'table', 'important');
        
        setTimeout(() => {
            if ($.fn.dataTable.isDataTable('#visitor_table')) {
                $('#visitor_table').DataTable().columns.adjust();
            }
        }, 10);
    }

    const recognitionZone = document.getElementById('visitor-recognition');
    if (recognitionZone) recognitionZone.style.display = 'none';
}

/* =========================================================================
   --- 9. DYNAMIC TRENDS REDIRECTION ---
   ========================================================================= */

// Double-clic sur une cellule de nom de joueur
$(document).on('dblclick', '.player-name-cell', function() {
    const playerName = $(this).text().trim();
    
    if (playerName) {
        // 1. On stocke le joueur uniquement pour la page Trends
        localStorage.setItem('selectedPlayer', playerName);
        
        // 2. Routage dynamique universel selon la saison (ex: index_lh01.html -> trends_lh01.html)
        let trendsPage = 'trends.html';
        const pageName = window.location.pathname.split('/').pop() || '';
        
        if (pageName.includes('_')) {
            const seasonSuffix = pageName.substring(pageName.indexOf('_') + 1).replace(/\.html$/i, '');
            trendsPage = `trends_${seasonSuffix}.html`;
        }
        
        // 3. Redirection directe vers le graphique de tendances
        window.location.href = `${trendsPage}#progressionChart`;
    }
});

/* =========================================================================
   --- 10. NARRATIVE JOURNEY RELATIONS TREE ---
   ========================================================================= */

function getRelationsIconHtml(tier) {
    if (!tier || tier === 'unranked' || typeof CONFIG === 'undefined' || !CONFIG.icons || !CONFIG.icons[tier]) return '';
    const iconUrl = CONFIG.icons[tier];
    return `<img src="${iconUrl}" class="tier-icon" alt="${tier}">`;
}

window.updateRelationsTree = function(playerName) {
    if (!window.relationsData) return;
    const data = window.relationsData[playerName];
    
    if (data) {
        document.getElementById('centerPlayerName').innerText = playerName;
        document.getElementById('centerPlayerMeta').innerHTML = `<div class="narrative-text">faced <span class="opponents-count">${data.unique_opponents}</span> different opponents...</div>`;
        
        // Trophy (Top Right)
        const nodeTrophy = document.getElementById('nodeTrophy');
        if (data.trophy && data.trophy.name) {
            const trophyIcon = data.trophy.tier ? getRelationsIconHtml(data.trophy.tier) : "";
            const eloColor = data.trophy.tier ? `var(--color-${data.trophy.tier})` : 'var(--text-main)';
            nodeTrophy.innerHTML = `
                <div class="narrative-text">...brought down the mighty</div>
                <div id="textTrophy" class="node-content-flex">
					${trophyIcon ? `<div class="node-icon-side">${trophyIcon}</div>` : ''}
					<div class="node-text-side">
						<div class="player-name">${data.trophy.name}</div>
						<div class="player-meta" style="color: ${eloColor};">${data.trophy.elo}</div>
					</div>
				</div>
            `;
            nodeTrophy.setAttribute('data-player', data.trophy.name);
        } else {
            nodeTrophy.innerHTML = `
                <div id="textTrophy">
                    <div class="narrative-text">...but failed to claim a single victory</div>
                </div>
            `;
            nodeTrophy.setAttribute('data-player', '');
        }
        
        // Bane (Bottom Right)
        const nodeBane = document.getElementById('nodeBane');
        if (data.bane && data.bane.name) {
            const baneIcon = data.bane.tier ? getRelationsIconHtml(data.bane.tier) : "";
            const eloColor = data.bane.tier ? `var(--color-${data.bane.tier})` : 'var(--text-main)';
            nodeBane.innerHTML = `
                <div class="narrative-text">...and fell before the humble</div>
                <div id="textBane" class="node-content-flex">
					${baneIcon ? `<div class="node-icon-side">${baneIcon}</div>` : ''}
					<div class="node-text-side">
						<div class="player-name">${data.bane.name}</div>
						<div class="player-meta" style="color: ${eloColor};">${data.bane.elo}</div>
					</div>
				</div>
            `;
            nodeBane.setAttribute('data-player', data.bane.name);
        } else {
            nodeBane.innerHTML = `
                <div id="textBane">
                    <div class="narrative-text">...and never once tasted defeat</div>
                </div>
            `;
            nodeBane.setAttribute('data-player', '');
        }
    }
};

// Fonction déclenchée quand on clique sur l'arbre (onclick)
window.selectPlayerFromTree = function(element) {
    const clickedName = element.getAttribute('data-player');
    if (clickedName) {
        const input = document.getElementById('playerName');
        input.value = clickedName;
        // Met à jour l'arbre
        window.updateRelationsTree(clickedName);
        // Force Chart.js à voir le changement
        input.dispatchEvent(new Event('input')); 
    }
};

// Fonction déclenchée quand on tape dans la barre (oninput)
window.updatePlayerView = function() {
    const currentPlayer = document.getElementById('playerName').value;
    if (currentPlayer) {
        window.updateRelationsTree(currentPlayer);
    }
};

// Initialisation intelligente
$(document).ready(function() {
    const input = document.getElementById('playerName');
    const savedPlayer = localStorage.getItem('selectedPlayer');
    
    // 1. Si la barre de recherche a une valeur (cache navigateur ou backend)
    if (input && input.value) {
        window.updatePlayerView();
    } 
    // 2. Sinon, on se rabat sur le localStorage
    else if (savedPlayer) {
        if (input) input.value = savedPlayer;
        window.updateRelationsTree(savedPlayer);
    }
});
