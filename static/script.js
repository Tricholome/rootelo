/* =========================================================================
   ROOTELO - JAVASCRIPT
   Table of Contents:
   1. Dynamic Scroll
   2. Double-tap
   3. Tier Modal
   4. Data Tables
   5. Chart
   6. Dynamic Trends
   7. Narrative Journey
   8. Global Player Search
   9. Match Simulator Engine
   10. Network Map & Table
   
   --- EASTER EGGS ---
   11. Secrets Engine
   12. Nut & Berry
   13. Visitor Recognition

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

		const tierColors = CONFIG.colors;
		const tierIcons = CONFIG.icons;

	window.openTierModal = function(tier) {
		const text = TIER_DATA[tier];
		const color = tierColors[tier] || tierColors['default'];
		const icon = tierIcons[tier];

		if (!text) return;

		const modalContent = modal.querySelector('.modal-content');
    	modalContent.style.setProperty('--tier-color', color);
		
		modalContent.classList.toggle('bear-shimmer', tier === 'bear');

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
		
		const modalFinal = document.getElementById('modalFinal');
		if (modalFinal) {
			modalFinal.innerHTML = text.final || '';
		}
		
		if (modalCrown) {
			modalCrown.src = text.crown || '';
			modalCrown.style.display = text.crown ? 'block' : 'none';
		}
		
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
		const pageName = window.location.pathname.split('/').pop() || '';
		let showAllPlayers = !pageName.includes('_'); 

		$('#tierFilterCheckbox').prop('checked', showAllPlayers);

		$.extend($.fn.dataTable.ext.type.order, { 
			"rank-pre": function (d) { 
				if (d === "♔") return 0; 
				if (d === "-" || d === "–" || d === "—") return 9999;
				return parseInt(d); 
			} 
		});

		$.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
			if (settings.nTable.id !== 'leaderboard') return true;
			if (showAllPlayers) return true; 
			const rowNode = settings.aoData[dataIndex].nTr;
			return rowNode && rowNode.dataset.tier !== 'unassigned';
		});

		const leaderboardTable = $('#leaderboard').DataTable({
			"order": [],
			"responsive": true, 
			"pageLength": 50,
			"dom": 'rt<"bottom"p><"clear">',
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
			]
		});

		leaderboardTable.draw();

		$(document).on('change', '#tierFilterCheckbox', function() {
			showAllPlayers = $(this).is(':checked');
			$('#leaderboard').DataTable().draw();
		});
	}

	// --- 2. MATCHES ---
	if ($('#matchesTable').length > 0) {
		$('#matchesTable').DataTable({
			"order": [[1, "desc"]], 
			"responsive": true,
			"pageLength": 50,
			"dom": 'rt<"bottom"p><"clear">',
			"columnDefs": [
				{ "className": "rank-cell", "targets": 0 },
				{ "className": "elo-sum-cell", "targets": 1 },
				{ "className": "date-cell", "targets": 2 },
				{ "className": "numeric-cell", "targets": [0, 1, 2, 5] },
				{ "responsivePriority": 1, "targets": [1, 4] },
				{ "responsivePriority": 2, "targets": [0, 2] },
				{ "responsivePriority": 3, "targets": [3, 5] }
			]
		});
	}
	
	// --- 3. SIMULATOR RESULT TABLE ---
	if ($('#simResultTable').length > 0) {
		$('#simResultTable').DataTable({
			"paging": false,
			"searching": false,
			"info": false,
			"ordering": false,
			"responsive": true,
			"dom": 'rt',
			"createdRow": function(row, data) {
            var val = parseFloat($('<div>' + data[4] + '</div>').text());
            
            if (!isNaN(val) && val < 0) {
                $(row).addClass('loser');
            }
        },
			"columnDefs": [
				{ "targets": 0, "className": "player-name-cell" },
				{ "className": "numeric-cell", "targets": [1, 2, 3, 4, 5] },
				{ "responsivePriority": 1, "targets": [0, 5] },
				{ "responsivePriority": 2, "targets": [4] },
				{ "responsivePriority": 3, "targets": [3] },
				{ "responsivePriority": 4, "targets": [1, 2] }
			]
		});
	}

    // --- 4. HALL OF FAME ---
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
	
	// --- 5. VISITOR TABLE ---
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
	
	// --- 6. GLOBAL FIX FOR ORIENTATION & RESIZE ---
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


/* =========================================================================
   --- 6. DYNAMIC TRENDS REDIRECTION ---
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
        window.location.href = `${trendsPage}#view`;
    }
});

/* =========================================================================
   --- 7. NARRATIVE JOURNEY RELATIONS TREE ---
   ========================================================================= */

function getRelationsIconHtml(tier) {
    if (!tier || tier === 'unranked' || typeof CONFIG === 'undefined' || !CONFIG.icons || !CONFIG.icons[tier]) return '';
    const iconUrl = CONFIG.icons[tier];
    return `<img src="${iconUrl}" class="tier-icon" alt="${tier}">`;
}

function getRandomVariation(array) {
    if (!array || array.length === 0) return "";
    return array[Math.floor(Math.random() * array.length)];
}

window.updateRelationsTree = function(playerName) {
    const relationsWrapper = document.querySelector('.relations-wrapper');
    
    if (!window.relationsData) {
        if (relationsWrapper) relationsWrapper.style.display = 'none';
        return;
    }
    
    const data = window.relationsData[playerName];
    const vars = window.NARRATIVE_VARIATIONS;
    
    if (!data || !data.unique_opponents || data.unique_opponents === 0) {
        if (relationsWrapper) relationsWrapper.style.display = 'none';
        return; 
    }
    
    if (relationsWrapper) relationsWrapper.style.display = 'block';
    
    document.getElementById('centerPlayerName').innerText = playerName;
    
    const introEl = document.getElementById('centerPlayerIntro');
    const metaEl = document.getElementById('centerPlayerMeta');
    const formattedCount = `<span class="opponents-count">${data.unique_opponents}</span>`;
    
    if (vars && vars.center && vars.opponents) {
        const centerIntro = getRandomVariation(vars.center);
        const opponentPhrase = getRandomVariation(vars.opponents).replace('{count}', formattedCount);
        
        if (introEl) introEl.innerHTML = centerIntro ? `<div class="narrative-text">${centerIntro}</div>` : '';
        if (metaEl) metaEl.innerHTML = opponentPhrase ? `<div class="narrative-text">${opponentPhrase}</div>` : '';
    } else {
        if (introEl) introEl.innerHTML = "";
        if (metaEl) metaEl.innerHTML = "";
    }
    
    // Logique du nœud Trophy (cible uniquement .node-content)
    const nodeTrophy = document.getElementById('nodeTrophy');
    if (nodeTrophy) {
        const target = nodeTrophy.querySelector('.node-content') || nodeTrophy;
        
        if (data.trophy && data.trophy.name) {
            const trophyIcon = data.trophy.tier ? getRelationsIconHtml(data.trophy.tier) : "";
            const eloColor = data.trophy.tier ? `var(--color-${data.trophy.tier})` : 'var(--text-main)';
            const trophyText = (vars && vars.trophy) ? getRandomVariation(vars.trophy) : "";
            
            target.innerHTML = `
                ${trophyText ? `<div class="narrative-text">${trophyText}</div>` : ''}
                <div id="textTrophy" class="node-content-flex">
                    ${trophyIcon ? `<div class="node-icon-side">${trophyIcon}</div>` : ''}
                    <div class="node-text-side">
                        <div class="player-name">${data.trophy.name}</div>
                        <div class="player-meta" style="color: ${eloColor};">Elo ${data.trophy.elo}</div>
                    </div>
                </div>
            `;
            nodeTrophy.setAttribute('data-player', data.trophy.name);
        } else {
            const trophyEmptyText = (vars && vars.trophy_empty) ? getRandomVariation(vars.trophy_empty) : "";
            target.innerHTML = `
                <div id="textTrophy">
                    ${trophyEmptyText ? `<div class="narrative-text">${trophyEmptyText}</div>` : ''}
                </div>
            `;
            nodeTrophy.setAttribute('data-player', '');
        }
    }
    
    // Logique du nœud Bane (cible uniquement .node-content)
    const nodeBane = document.getElementById('nodeBane');
    if (nodeBane) {
        const target = nodeBane.querySelector('.node-content') || nodeBane;
        
        if (data.bane && data.bane.name) {
            const baneIcon = data.bane.tier ? getRelationsIconHtml(data.bane.tier) : "";
            const eloColor = data.bane.tier ? `var(--color-${data.bane.tier})` : 'var(--text-main)';
            const baneText = (vars && vars.bane) ? getRandomVariation(vars.bane) : "";
            
            target.innerHTML = `
                ${baneText ? `<div class="narrative-text">${baneText}</div>` : ''}
                <div id="textBane" class="node-content-flex">
                    ${baneIcon ? `<div class="node-icon-side">${baneIcon}</div>` : ''}
                    <div class="node-text-side">
                        <div class="player-name">${data.bane.name}</div>
                        <div class="player-meta" style="color: ${eloColor};">Elo ${data.bane.elo}</div>
                    </div>
                </div>
            `;
            nodeBane.setAttribute('data-player', data.bane.name);
        } else {
            const baneEmptyText = (vars && vars.bane_empty) ? getRandomVariation(vars.bane_empty) : "";
            target.innerHTML = `
                <div id="textBane">
                    ${baneEmptyText ? `<div class="narrative-text">${baneEmptyText}</div>` : ''}
                </div>
            `;
            nodeBane.setAttribute('data-player', '');
        }
    }
};

window.selectPlayerFromTree = function(element) {
    const clickedName = element.getAttribute('data-player');
    if (clickedName) {
        const input = document.getElementById('playerName');
        input.value = clickedName;
        window.updateRelationsTree(clickedName);
        input.dispatchEvent(new Event('input')); 
    }
};

window.updatePlayerView = function() {
    const input = document.getElementById('playerName');
    const currentPlayer = input ? input.value.trim() : "";
    
    const chartWrapper = document.querySelector('.chart-wrapper');
    const relationsWrapper = document.querySelector('.relations-wrapper');

    if (currentPlayer) {
        if (chartWrapper) chartWrapper.style.display = 'block';
        if (relationsWrapper) relationsWrapper.style.display = 'block';
        window.updateRelationsTree(currentPlayer);
    } else {
        if (chartWrapper) chartWrapper.style.display = 'none';
        if (relationsWrapper) relationsWrapper.style.display = 'none';
        
        const centerName = document.getElementById('centerPlayerName');
        const centerIntro = document.getElementById('centerPlayerIntro');
        const centerMeta = document.getElementById('centerPlayerMeta');
        
        if (centerName) centerName.innerText = 'Select a player';
        if (centerIntro) centerIntro.innerHTML = '';
        if (centerMeta) centerMeta.innerHTML = '';

        const nodeTrophy = document.getElementById('nodeTrophy');
        if (nodeTrophy) {
            const target = nodeTrophy.querySelector('.node-content') || nodeTrophy;
            target.innerHTML = `
                <div id="textTrophy">
                    <div class="player-name">...</div>
                </div>
            `;
            nodeTrophy.setAttribute('data-player', '');
        }

        const nodeBane = document.getElementById('nodeBane');
        if (nodeBane) {
            const target = nodeBane.querySelector('.node-content') || nodeBane;
            target.innerHTML = `
                <div id="textBane">
                    <div class="player-name">...</div>
                </div>
            `;
            nodeBane.setAttribute('data-player', '');
        }
    }
};

/* =========================================================================
   --- 8. GLOBAL PLAYER SEARCH & PERSISTENCE SYNC ---
   ========================================================================= */

$(document).ready(function() {
    const input = document.getElementById('playerName');
    if (!input) return;

    const profileMap = window.PLAYER_PROFILE_MAP || {};

    function getCanonicalName(query) {
        if (!query) return "";
        const q = query.trim().toLowerCase();

        for (const [name, slug] of Object.entries(profileMap)) {
            if (name.toLowerCase() === q || (slug && String(slug).toLowerCase() === q)) {
                return name;
            }
        }
        return query;
    }

    function applyGlobalSearch(val) {
        const query = (val || "").trim();
        const cleanName = getCanonicalName(query);
        const slug = profileMap[cleanName];

        const dbBtn = document.getElementById('root-db-btn');
        if (dbBtn) {
            if (slug) {
                const baseUrl = (window.PROFILE_BASE_URL || '').replace(/\/+$/, '');
                dbBtn.href = `${baseUrl}/${slug}`;
                dbBtn.classList.remove('disabled');
                dbBtn.style.opacity = '1';
                dbBtn.style.pointerEvents = 'auto';
            } else {
                dbBtn.href = '#';
                dbBtn.classList.add('disabled');
                dbBtn.style.opacity = '0.4';
                dbBtn.style.pointerEvents = 'none';
            }
        }

        if (cleanName) {
            localStorage.setItem('selectedPlayer', cleanName);
            const tierCheckbox = $('#tierFilterCheckbox');
            if (tierCheckbox.length > 0 && !tierCheckbox.is(':checked')) {
                tierCheckbox.prop('checked', true).trigger('change');
            }
        } else {
            localStorage.removeItem('selectedPlayer');
        }

        $('.dataTable').each(function() {
            if ($.fn.dataTable.isDataTable(this)) {
                $(this).DataTable().search(cleanName).draw();
            }
        });

        if (typeof window.updatePlayerView === 'function') window.updatePlayerView();
        if (typeof window.updateChart === 'function' && document.getElementById('progressionChart')) window.updateChart();
    }

    $(input).on('input change', function() {
        applyGlobalSearch(this.value);
    });

    const urlParam = new URLSearchParams(window.location.search).get('player');
    const savedPlayer = localStorage.getItem('selectedPlayer');
    const initialQuery = urlParam || savedPlayer || "";

    if (initialQuery) {
        const cleanName = getCanonicalName(initialQuery);
        input.value = cleanName;
        setTimeout(() => applyGlobalSearch(cleanName), 50);
    } else {
        applyGlobalSearch("");
    }
});

/* =========================================================================
   --- 9. MATCH SIMULATOR ENGINE ---
   ========================================================================= */

$(document).ready(function() {
    if ($('#simTable').length === 0 || $('#simResultTable').length === 0) return;

    const REQUIRED_K_KEYS = ['k_floor', 'k_start', 'exp_decay', 'k_cap_ranked', 'k_cap_new'];
    const kConfig = window.K_CONFIG || {};

    const isConfigValid = REQUIRED_K_KEYS.every(
        key => key in kConfig && kConfig[key] !== null && kConfig[key] !== undefined && kConfig[key] !== ''
    );

    if (!isConfigValid) {
        console.warn("Simulator disabled: Missing K_CONFIG keys in league.json", kConfig);
        $('#simTable, #simResultTable').hide();
        return;
    }

    const playerData = window.PLAYER_DATA_MAP || {};

    function calculateKFactor(gamesCount, isRanked) {
        const kFloor = parseFloat(kConfig.k_floor);
        const kStart = parseFloat(kConfig.k_start);
        const expDecay = parseFloat(kConfig.exp_decay);
        const kCap = parseFloat(kConfig[isRanked ? 'k_cap_ranked' : 'k_cap_new']);

        const kBase = kFloor + (kStart - kFloor) * Math.exp(-gamesCount / expDecay);
        return Math.min(kCap, kBase);
    }

    function getTierFromElo(elo, gamesCount) {
        if (gamesCount < 10) return 'unassigned';
        if (elo >= 1600) return 'stag';
        if (elo >= 1500) return 'bird';
        if (elo >= 1400) return 'fox';
        if (elo >= 1300) return 'rabbit';
        if (elo >= 1200) return 'mouse';
        return 'squirrel';
    }

    function renderTierCell(elo, gamesCount) {
        const tier = getTierFromElo(elo, gamesCount);
        
        if (tier === 'unassigned' || typeof CONFIG === 'undefined' || !CONFIG.icons || !CONFIG.icons[tier]) {
            return elo.toString();
        }

        const templateEl = document.getElementById('simTierTemplate');
        if (!templateEl) return elo.toString();

        return templateEl.innerHTML
            .replaceAll('{TIER}', tier)
            .replace('{ICON_URL}', CONFIG.icons[tier])
            .replace('{ELO}', elo);
    }

    $(document).on('change', '.sim-winner-toggle', function() {
        const checkedToggles = $('.sim-winner-toggle:checked');
        
        if (checkedToggles.length > 2) {
            $(this).prop('checked', false);
            return;
        }
        
        runSimulation();
    });

    $(document).on('input change', '.sim-p-name', function() {
        const row = $(this).closest('tr');
        const typedName = $(this).val().trim();
        
        const matchedKey = Object.keys(playerData).find(
            key => key.toLowerCase() === typedName.toLowerCase()
        );

        if (matchedKey) {
            const info = playerData[matchedKey];
            row.find('.sim-p-elo').val(info.elo);
            row.find('.sim-p-games').val(info.games);
            row.data('is_ranked', info.is_ranked || false);
        } else {
            row.data('is_ranked', false);
        }
        runSimulation();
    });

    function runSimulation() {
        const rows = $('#simTable tbody tr');
        const players = [];

        const winnerCount = $('.sim-winner-toggle:checked').length;
        const scorePerWinner = winnerCount > 0 ? (1.0 / winnerCount) : 0.0;

        rows.each(function(index) {
            const row = $(this);
            const isWinner = row.find('.sim-winner-toggle').is(':checked');
            const name = row.find('.sim-p-name').val().trim() || `Player ${index + 1}`;
            const elo = parseFloat(row.find('.sim-p-elo').val()) || 1200;
            const games = parseInt(row.find('.sim-p-games').val(), 10) || 0;
            const isRanked = row.data('is_ranked') || false;

            players.push({
                name: name,
                elo: elo,
                games: games,
                isRanked: isRanked,
                actualScore: isWinner ? scorePerWinner : 0.0
            });
        });

        if (players.length === 0) return;

        const qScores = players.map(p => Math.pow(10, p.elo / 400));
        const totalQ = qScores.reduce((sum, q) => sum + q, 0);

		const formattedData = players.map((p, i) => {
			const expected = totalQ > 0 ? (qScores[i] / totalQ) : (1 / players.length);
			const k = calculateKFactor(p.games, p.isRanked);
			const change = k * (p.actualScore - expected);
			
			const roundDelta = Math.round(change);
			const currentEloRounded = Math.round(p.elo);
			const newEloRounded = Math.round(p.elo + change);
			
			const winProbStr = (expected * 100).toFixed(1) + '%';

			const deltaSign = roundDelta >= 0 ? '+' : '';
			const deltaHtml = `${deltaSign}${roundDelta}`;

			return [
				p.name,
				renderTierCell(currentEloRounded, p.games),
				Math.round(k * 10) / 10,
				winProbStr,
				deltaHtml,
				renderTierCell(newEloRounded, p.games + 1)
			];
		});

        const simResultTable = $('#simResultTable').DataTable();
        simResultTable.clear();
        simResultTable.rows.add(formattedData);
        simResultTable.draw();
    }

    $(document).on('input change', '.sim-p-elo, .sim-p-games', runSimulation);

    runSimulation();
});

/* =========================================================================
   --- 11. SECRETS ENGINE ---
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
            document.title = "Rootelo • Glade of Fame";
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
   --- 12. NUT & BERRY ---
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
   --- 13. VISITOR RECOGNITION ---
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
   --- 10. NETWORK MAP & TABLE ---
   ========================================================================= */

$(document).ready(function () {
    // 1. Guard Clause & Extraction des données globales
    const dates = window.NETWORK_DATES;
    const snapshots = window.NETWORK_SNAPSHOTS;
    const config = window.NETWORK_CONFIG || { tribes: {}, tiers: {} };

    if (!dates || !dates.length || !snapshots) return;

    // --- Variables d'état ---
    const TARGET_TRIBES = Object.keys(config.tribes || {});
    const centerCols = TARGET_TRIBES.map((_, i) => i + 1);
    let activeTribeFilter = null;
    let simulation = null;
    let currentIndex = dates.length - 1;

    // --- Éléments DOM ---
    const $datePicker = $('#datePicker').attr({ min: dates[0], max: dates[dates.length - 1] });
    const $prevBtn = $('#prevDateBtn');
    const $nextBtn = $('#nextDateBtn');
    const $earliestBtn = $('#earliestDateBtn');
    const $latestBtn = $('#latestDateBtn');

    /* -------------------------------------------------------------------------
       10.1 DATA TABLE MANAGEMENT
       ------------------------------------------------------------------------- */
    const table = $('#frogTable').DataTable({
        "order": [[1, "desc"]],
        "responsive": false,
        "autoWidth": false,
        "pageLength": 50,
        "dom": 'rt<"bottom"p><"clear">',
        "columnDefs": [
            { "className": "dt-nowrap", "targets": "_all" },
            { "className": "dt-center", "targets": centerCols }
        ]
    });

    function getBadgeColor(status) {
        return config.tiers?.[status] || config.tiers?.Default || "#4a5568";
    }

    function renderTribeCell(scoreData, isMainTribe) {
        if (!scoreData || (!isMainTribe && scoreData.pct < 10)) {
            return `<div class="tribe-cell-empty">-</div>`;
        }
        const pctStr = `<span class="tribe-pct">${scoreData.pct}%</span>`;
        if (!isMainTribe || !scoreData.status) {
            return `<div class="tribe-cell">${pctStr}</div>`;
        }
        return `<div class="tribe-cell">${pctStr} <span class="tribe-badge" style="background-color: ${getBadgeColor(scoreData.status)};">${scoreData.status}</span></div>`;
    }

    function updateTable(snapshot) {
        const activeTribes = snapshot.active_tribes || [];

        TARGET_TRIBES.forEach((tribe, idx) => {
            const colIdx = idx + 2;
            const isActive = activeTribes.includes(tribe);
            table.column(colIdx).visible(isActive, false);

            if (isActive) {
                const label = snapshot.tribe_labels?.[tribe] || tribe;
                const icon = config.tribes[tribe]?.icon || '';
                $(table.column(colIdx).header()).html(`<img src="${icon}" title="${label}" alt="${label}" class="tribe-icon">`);
            }
        });

        let players = snapshot.players || [];
        if (activeTribeFilter) {
            players = players.filter(p => p.main_tribe === activeTribeFilter);
        }

        const rows = players.map(p => [
            p.name,
            p.games,
            ...TARGET_TRIBES.map(t => renderTribeCell(p.scores?.[t], p.main_tribe === t))
        ]);

        table.clear().rows.add(rows).columns.adjust().draw();
    }

    /* -------------------------------------------------------------------------
       10.2 GRAPH DATA GENERATOR
       ------------------------------------------------------------------------- */

    // Un seul endroit pour définir ce qu'est un pilier / satellite / membre :
    // rayon de la bulle ET distance d'orbite autour du hub de la tribu.
    // (radius du hub lui-même reste calculé séparément, via tribeRadius().)
    const TIERS = {
        pillar: { radius: 20, dist: 85 },
        satellite: { radius: 12, dist: 130 },
        member: { radius: 7, dist: 170 }
    };

    function tribeRadius(count) {
        return Math.max(32, 24 + Math.sqrt(count || 0) * 10);
    }

    function buildGraphData(snapshot) {
        const activeTribes = snapshot.active_tribes || [];
        const tribeLayout = snapshot.tribe_layout || {};
        const nodes = [];
        const links = [];

        if (!activeTribeFilter) {
            // --- Vue Globale : une bulle par tribu ---
            activeTribes.forEach(t => {
                const count = snapshot.summary?.[t] || 0;
                nodes.push({
                    id: t,
                    type: 'tribe',
                    label: snapshot.tribe_labels?.[t] || t,
                    count: count,
                    radius: tribeRadius(count)
                });
            });

            for (let i = 0; i < activeTribes.length; i++) {
                for (let j = i + 1; j < activeTribes.length; j++) {
                    const t1 = activeTribes[i];
                    const t2 = activeTribes[j];
                    let totalAffinity = 0, count = 0;

                    (snapshot.players || []).forEach(p => {
                        if (p.main_tribe === t1 && p.scores?.[t2]) {
                            totalAffinity += p.scores[t2].pct; count++;
                        } else if (p.main_tribe === t2 && p.scores?.[t1]) {
                            totalAffinity += p.scores[t1].pct; count++;
                        }
                    });

                    const avg = count > 0 ? totalAffinity / count : 0;
                    if (avg > 2) {
                        links.push({ source: t1, target: t2, value: avg, type: 'inter-tribe' });
                    }
                }
            }
            return { nodes, links };
        }

        // --- Vue Constellation : une tribu + ses membres, classés par palier ---
        const tribe = activeTribeFilter;
        const count = snapshot.summary?.[tribe] || 0;
        const layout = tribeLayout[tribe] || { pillars: [], satellites: [] };
        const pillarsSet = new Set(layout.pillars || []);
        const satellitesSet = new Set(layout.satellites || []);

        nodes.push({
            id: tribe,
            type: 'tribe',
            label: snapshot.tribe_labels?.[tribe] || tribe,
            count: count,
            radius: tribeRadius(count)
        });

        // Un membre = un palier (pillar / satellite / member), triés par nom
        // pour que l'ordre autour du cercle reste stable d'un jour à l'autre
        // (sinon tout le monde tourne dès qu'un joueur change de statut).
        const tiered = { pillar: [], satellite: [], member: [] };
        (snapshot.players || [])
            .filter(p => p.main_tribe === tribe)
            .sort((a, b) => a.name.localeCompare(b.name))
            .forEach(p => {
                const tier = pillarsSet.has(p.name) ? 'pillar'
                    : satellitesSet.has(p.name) ? 'satellite'
                        : 'member';
                tiered[tier].push(p);
            });

        // Hash déterministe (0..1) dérivé du nom : donne un écart "aléatoire"
        // mais stable d'un jour à l'autre (même joueur -> même écart), pour
        // ne pas faire sauter tout le monde à chaque re-rendu.
        function nameJitter01(name) {
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = (Math.imul(hash, 31) + name.charCodeAt(i)) >>> 0;
            }
            return (hash % 10000) / 10000;
        }

        // Répartition par palier : chaque palier (pillar / satellite / member)
        // est distribué sur son PROPRE cercle complet (0→360°), indépendamment
        // des autres. Un round-robin à compteur partagé entre paliers de
        // tailles très inégales (les piliers, toujours peu nombreux, plafonnés
        // à 6) s'épuise après quelques tours : les piliers se retrouvaient
        // compressés dans les ~12 premiers % du cercle au lieu d'être répartis
        // sur 360°. Comme les paliers ont des rayons d'orbite différents
        // (TIERS[tier].dist), ils forment déjà des anneaux concentriques
        // distincts — inutile de les entrelacer sur un même indice global pour
        // éviter les arcs, il suffit que chaque anneau soit uniforme.
        //
        // Deux ajustements pour un rendu organique plutôt que "roue à
        // rayons" (surtout visible quand un palier a peu de membres) :
        // - un déphasage fixe différent par palier, pour que pillar/
        //   satellite/member ne démarrent pas tous les trois à midi ;
        // - un jitter stable (basé sur le nom) qui casse l'espacement
        //   parfaitement régulier au sein d'un même palier.
        const TIER_PHASE = { pillar: 0, satellite: 0.22, member: 0.47 }; // fraction de tour

        ['pillar', 'satellite', 'member'].forEach(tier => {
            const group = tiered[tier];
            const { radius, dist } = TIERS[tier];
            const total = group.length || 1;
            const slot = (2 * Math.PI) / total;
            const phase = TIER_PHASE[tier] * 2 * Math.PI;

            group.forEach((player, idx) => {
                const scoreObj = player.scores?.[tribe];
                const jitter = (nameJitter01(player.name) - 0.5) * slot * 0.7; // ±35% du slot, pas de collision
                const angle = phase + (slot * idx) + jitter - (Math.PI / 2);
                const playerId = `player_${player.name}`;

                nodes.push({
                    id: playerId,
                    type: 'player',
                    name: player.name,
                    tier,
                    pct: scoreObj?.pct || 0,
                    status: scoreObj?.status || null,
                    color: getBadgeColor(scoreObj?.status),
                    radius,
                    dist,
                    angle
                });

                links.push({ source: tribe, target: playerId, tier });
            });
        });

        return { nodes, links };
    }

    /* -------------------------------------------------------------------------
       10.3 D3 NETWORK GRAPH ENGINE
       ------------------------------------------------------------------------- */
    function renderTribeGraph(snapshot) {
        if (typeof d3 === 'undefined') return;

        const svg = d3.select("#tribeMapSvg");
        const container = document.getElementById('tribeMapContainer');
        const width = container?.clientWidth || 800;
        const height = 380;
        const duration = 400;

        if (svg.select("g.links-layer").empty()) {
            svg.append("g").attr("class", "links-layer");
            svg.append("g").attr("class", "nodes-layer");
        }

        const { nodes: newNodes, links: newLinks } = buildGraphData(snapshot);

        // Conserve la position des nœuds déjà présents (transition douce),
        // place les nouveaux au point d'entrée (hub actif ou centre).
        const prevNodesMap = new Map(simulation ? simulation.nodes().map(d => [d.id, d]) : []);
        let originX = width / 2, originY = height / 2;
        if (activeTribeFilter && prevNodesMap.has(activeTribeFilter)) {
            const prevTribe = prevNodesMap.get(activeTribeFilter);
            originX = prevTribe.x;
            originY = prevTribe.y;
        }
        newNodes.forEach(d => {
            const prev = prevNodesMap.get(d.id);
            if (prev) {
                // Nœud déjà présent : on part de sa position précédente.
                d.x = prev.x; d.y = prev.y;
            } else if (d.type === 'player' && d.dist != null) {
                // Nouveau membre : on le fait naître directement sur son
                // orbite cible (même angle/distance que ceux utilisés par
                // forceRadial) plutôt que collé au hub. Sinon, plusieurs
                // nœuds démarrant à distance ~0 du hub font diverger
                // forceRadial (division par une distance quasi nulle) et
                // les bulles partent hors du conteneur.
                d.x = originX + d.dist * Math.cos(d.angle);
                d.y = originY + d.dist * Math.sin(d.angle);
            } else {
                // Nouvelle bulle de tribu : léger écart aléatoire pour la
                // même raison (éviter une superposition exacte avec une
                // autre bulle).
                d.x = originX + (Math.random() - 0.5) * 10;
                d.y = originY + (Math.random() - 0.5) * 10;
            }
        });

        const drag = d3.drag()
            .on("start", (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on("end", (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; });

        // --- Liens ---
        const linkSel = svg.select("g.links-layer").selectAll("line")
            .data(newLinks, d => `${d.source.id || d.source}-${d.target.id || d.target}`);

        linkSel.exit().transition().duration(duration).attr("stroke-opacity", 0).remove();

        const link = linkSel.enter().append("line").merge(linkSel);
        link.attr("class", d => `link ${d.type || 'constellation-link'} ${d.tier ? 'tier-' + d.tier : ''}`);

        // --- Nœuds ---
        const nodeSel = svg.select("g.nodes-layer").selectAll("g.node-group")
            .data(newNodes, d => d.id);

        nodeSel.exit().transition().duration(duration).style("opacity", 0).remove();

        const nodeEnter = nodeSel.enter().append("g").call(drag);
        nodeEnter.append("circle").attr("class", "node-circle");
        nodeEnter.append("image").attr("class", "node-icon");

        const textGroup = nodeEnter.append("text").attr("class", "count-text");
        textGroup.append("tspan").attr("class", "num-span").attr("x", 0).attr("dy", "0");
        textGroup.append("tspan").attr("class", "lbl-span").attr("x", 0).attr("dy", "1.2em");

        nodeEnter.append("text").attr("class", "player-label");

        const node = nodeEnter.merge(nodeSel);

        node.attr("class", d => `node-group type-${d.type} tier-${d.tier || 'hub'} ${activeTribeFilter === d.id ? 'is-selected' : ''}`)
            .style("--node-color", d => d.color || null)
            .transition().duration(duration).style("opacity", 1);

        node.each(function (d) {
            const g = d3.select(this);
            g.select(".node-circle").transition().duration(duration).attr("r", d.radius);

            if (d.type === 'tribe') {
                const iconPath = config.tribes?.[d.id]?.icon || '';
                const iconSize = Math.max(24, d.radius * 0.7);
                g.select(".node-icon")
                    .attr("href", iconPath).attr("xlink:href", iconPath)
                    .attr("width", iconSize).attr("height", iconSize)
                    .attr("x", -iconSize / 2).attr("y", -iconSize / 2 - 6);
                g.select(".count-text").attr("transform", `translate(0, ${iconSize / 2 + 8})`);
                g.select(".num-span").text(d.count);
                g.select(".lbl-span").text(" members");
            } else {
                const labelClass = d.tier === 'pillar' ? "player-label pillar-label"
                    : d.tier === 'satellite' ? "player-label satellite-label"
                        : "player-label member-label";
                g.select(".player-label").text(d.name).attr("class", labelClass);
            }
        });

        node.on("click", (event, d) => {
            if (event.defaultPrevented || d.type !== 'tribe') return;
            activeTribeFilter = (activeTribeFilter === d.id) ? null : d.id;
            updateView(dates[currentIndex]);
        });

        // --- Simulation physique ---
        if (!simulation) {
            simulation = d3.forceSimulation().alphaDecay(0.05);
        }
        // Le lien est créé sans sa liste de liens : il ne doit résoudre les
        // identifiants source/target qu'une fois que la simulation connaît
        // déjà les nœuds de CE rendu (simulation.nodes(newNodes) plus bas).
        // Sinon d3 cherche ces identifiants dans l'ancien jeu de nœuds (ou
        // dans un jeu vide au tout premier rendu) et lève une erreur.
        const linkForce = d3.forceLink().id(d => d.id);

        if (!activeTribeFilter) {
            // Vue globale : disposition libre, légèrement recentrée.
            simulation
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("radial", null)
                .force("link", linkForce.distance(145))
                .force("charge", d3.forceManyBody().strength(-320))
                .force("collision", d3.forceCollide().radius(d => d.radius + 15));
        } else {
            // Vue constellation : chaque membre orbite le hub à une distance
            // fixe selon son palier. Cette distance est appliquée "à la
            // main" dans le tick handler plus bas plutôt que via
            // d3.forceRadial : cette force-là ne relit son centre qu'UNE
            // fois, à l'initialisation, puis le fige — si le hub bouge
            // ensuite (et il bouge), les membres continuent à s'accrocher à
            // son ancienne position. D'où l'effondrement dans un coin.
            simulation
                .force("center", null)
                .force("link", linkForce.distance(0).strength(0)) // purement visuel, la distance réelle est gérée dans le tick
                .force("charge", d3.forceManyBody().strength(d => d.type === 'tribe' ? 0 : -25))
                .force("radial", null)
                .force("x", d3.forceX(width / 2).strength(d => d.type === 'tribe' ? 0.3 : 0))
                .force("y", d3.forceY(height / 2).strength(d => d.type === 'tribe' ? 0.3 : 0))
                .force("collision", d3.forceCollide().radius(d => d.radius + 6));
        }

        simulation.nodes(newNodes);
        simulation.force("link").links(newLinks);
        simulation.alpha(0.5).restart();

        simulation.on("tick", () => {
            // Orbite des membres autour du hub, recalculée sur sa position
            // COURANTE à chaque image (jamais mise en cache).
            if (activeTribeFilter) {
                const hub = newNodes.find(n => n.id === activeTribeFilter);
                if (hub) {
                    newNodes.forEach(d => {
                        if (d.type !== 'player' || d.dist == null || d.fx != null) return;
                        const dx = d.x - hub.x, dy = d.y - hub.y;
                        const r = Math.sqrt(dx * dx + dy * dy) || 1e-6;
                        const k = (d.dist - r) / r * 0.12; // rappel doux, pas un claquement brutal
                        d.x += dx * k;
                        d.y += dy * k;
                    });
                }
            }

            // Filet de sécurité : aucune bulle ne sort du cadre visible.
            newNodes.forEach(d => {
                d.x = Math.max(d.radius, Math.min(width - d.radius, d.x));
                d.y = Math.max(d.radius, Math.min(height - d.radius, d.y));
            });

            // --- CALCUL PRÉCIS DU DÉPART ET DE L'ARRIVÉE DES LIGNES ---
            link
                .attr("x1", d => {
                    const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.source.x + (dx / dist) * (d.source.radius || 0);
                })
                .attr("y1", d => {
                    const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.source.y + (dy / dist) * (d.source.radius || 0);
                })
                .attr("x2", d => {
                    const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.x - (dx / dist) * (d.target.radius || 0);
                })
                .attr("y2", d => {
                    const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.y - (dy / dist) * (d.target.radius || 0);
                });

            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });
    }

    /* -------------------------------------------------------------------------
       10.4 TIMELINE & CONTROLS
       ------------------------------------------------------------------------- */
    function updateView(selectedDate) {
        $datePicker.val(selectedDate);
        const snapshot = snapshots[selectedDate];
        if (!snapshot) return;

        renderTribeGraph(snapshot);
        updateTable(snapshot);

        $prevBtn.prop('disabled', currentIndex <= 0);
        $nextBtn.prop('disabled', currentIndex >= dates.length - 1);
    }

    function setDateByIndex(index) {
        if (index >= 0 && index < dates.length) {
            currentIndex = index;
            updateView(dates[currentIndex]);
        }
    }

    // Écouteurs d'événements UI
    $prevBtn.on('click', () => setDateByIndex(currentIndex - 1));
    $nextBtn.on('click', () => setDateByIndex(currentIndex + 1));
    $earliestBtn.on('click', () => setDateByIndex(0));
    $latestBtn.on('click', () => setDateByIndex(dates.length - 1));

    $datePicker.on('change', function () {
        const val = $(this).val();
        const matchIdx = dates.findIndex(d => d >= val);
        currentIndex = matchIdx !== -1 ? matchIdx : dates.length - 1;
        updateView(dates[currentIndex]);
    });

    $(window).on('resize', () => {
        if (dates[currentIndex]) updateView(dates[currentIndex]);
    });

    // Lancement
    setDateByIndex(currentIndex);
});
