/* =========================================================================
   ROOTELO - JAVASCRIPT
   Table of Contents:
   1.  Dynamic Scroll
   2.  Double-tap
   3.  Tier Modal
   4.  Data Tables
   5.  Chart
   6.  Dynamic Trends
   7.  Narrative Journey
   8.  Global Player Search
   9.  Match Simulator Engine
   10. Homelands Map & Player Network Engines
   
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
   --- 10. HOMELANDS MAP & PLAYER NETWORK ENGINE ---
   ========================================================================= */

$(document).ready(function () {
    const dates = window.NETWORK_DATES;
    const snapshots = window.NETWORK_SNAPSHOTS;
    const config = window.NETWORK_CONFIG || {};
    const constellations = window.PLAYER_CONSTELLATIONS?.players || {};

    if (!dates?.length || !snapshots) return;

    const { same_tribe, other_tribe, unaligned } = config.colors;
    const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
    const TIER_PHASE = { core: 0, mid: 0.22, outer: 0.47 };

    let currentView = 'hm';
    let activeTribe = null;
    let selectedPlayer = null;
    let currentIndex = dates.length - 1;
    let lastRenderedView = null;
    let simulation = null;

    const $wrapper = $('#networkWrapper');
    const $datePicker = $('#datePicker').attr({ min: dates[0], max: dates[dates.length - 1] });
    const $prevBtn = $('#prevDateBtn');
    const $nextBtn = $('#nextDateBtn');
    const $earliestBtn = $('#earliestDateBtn');
    const $latestBtn = $('#latestDateBtn');
    const $headerTitle = $('#mapHeaderTitle');
    const $legend = $('#mapLegend');
    const $searchInput = $('#playerName');
    const $ledger = $('#playerLedger');

    // --- Helpers & Math Utilities ---
    const normalizeTribe = t => (!t || t === '-' || t === 'UNALIGNED') ? null : t;
    const getPlayerTribe = name => normalizeTribe(constellations[name]?.tribe);
    const tribeRadius = count => Math.max(32, 24 + Math.sqrt(count || 0) * 10);
    const partnerRadius = games => Math.min(24, 6 + Math.sqrt(Math.max(1, games)) * 3);
    const centerRadius = (games, maxPRad) => Math.max(18, Math.min(30, 12 + Math.sqrt(Math.max(1, games)) * 2.2), (maxPRad || 10) + 3);

    function fidelityColor(fidelity) {
        const pct = Math.round(Math.max(0, Math.min(1, ((Number(fidelity) || 0) - 35) / 60)) * 100);
        return `color-mix(in srgb, ${same_tribe} ${pct}%, ${other_tribe})`;
    }

    function networkColor(centerTribe, nodeTribe, isCenter) {
        if (isCenter) return centerTribe ? same_tribe : unaligned;
        if (!nodeTribe) return unaligned;
        return (centerTribe && nodeTribe === centerTribe) ? same_tribe : other_tribe;
    }

    function nameJitter(name) {
        let h = 0;
        for (let i = 0; i < name.length; i++) h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0;
        return (h % 10000) / 10000;
    }

    function formatShortDate(dateStr) {
        const d = new Date(`${dateStr}T00:00:00`);
        return isNaN(d) ? dateStr : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    function distToSegment(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1, dy = y2 - y1, lenSq = dx * dx + dy * dy;
        if (!lenSq) return Math.hypot(px - x1, py - y1);
        const t = Math.max(0.05, Math.min(0.95, ((px - x1) * dx + (py - y1) * dy) / lenSq));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }

    function findPlayer(query) {
        const q = (query || '').trim();
        if (!q) return null;
        if (constellations[q]) return { name: q, data: constellations[q] };
        const low = q.toLowerCase();
        const key = Object.keys(constellations).find(k => k.toLowerCase() === low);
        return key ? { name: key, data: constellations[key] } : null;
    }

	// --- Historical Lifespan & Chronicle Queries ---
    function getTribeLifespan(tribe) {
        if (!tribe) return null;
        const activeIndices = [];
        const segments = [];
        let currentSeg = null;
        let peakIndex = -1, peakCount = 0;

        dates.forEach((d, idx) => {
            const members = (snapshots[d]?.[tribe] || []).map(m => m[0]);
            if (members.length > 0) {
                activeIndices.push(idx);
                if (members.length > peakCount) {
                    peakCount = members.length;
                    peakIndex = idx;
                }
                if (currentSeg) {
                    currentSeg.endIndex = idx;
                    members.forEach(p => currentSeg.allMembers.add(p));
                } else {
                    currentSeg = {
                        startIndex: idx,
                        endIndex: idx,
                        startMembers: new Set(members),
                        allMembers: new Set(members)
                    };
                    segments.push(currentSeg);
                }
            } else {
                currentSeg = null;
            }
        });

        if (!activeIndices.length) return null;

        const milestones = [];
        const historicalMembers = new Set();

        segments.forEach((seg, segIdx) => {
            if (segIdx === 0) {
                milestones.push({
                    idx: seg.startIndex,
                    label: `Founded ${formatShortDate(dates[seg.startIndex])}`,
                    title: 'Jump to founding date'
                });
            } else {
                const overlap = [...seg.startMembers].filter(p => historicalMembers.has(p)).length;
                const isRevival = overlap >= 3;
                const actionLabel = isRevival ? 'Revived' : 'Reclaimed';
                const actionTitle = isRevival
                    ? `Jump to revival (${overlap} returning members)`
                    : 'Jump to reclamation by a new fellowship';

                milestones.push({
                    idx: seg.startIndex,
                    label: `${actionLabel} ${formatShortDate(dates[seg.startIndex])}`,
                    title: actionTitle
                });
            }

            seg.allMembers.forEach(p => historicalMembers.add(p));

            if (peakIndex > seg.startIndex && peakIndex < seg.endIndex) {
                milestones.push({
                    idx: peakIndex,
                    label: `Culminated ${formatShortDate(dates[peakIndex])}`,
                    title: `Jump to peak membership: ${peakCount} denizens`
                });
            }

            if (seg.endIndex < dates.length - 1) {
                const dissolvedDate = dates[seg.endIndex + 1] || dates[seg.endIndex];
                milestones.push({
                    idx: seg.endIndex,
                    label: `Dissolved ${formatShortDate(dissolvedDate)}`,
                    title: 'Jump to final active day'
                });
            }
        });

        return {
            activeIndices,
            firstIndex: activeIndices[0],
            lastIndex: activeIndices[activeIndices.length - 1],
            milestones
        };
    }

    // --- UI Context Updaters ---
    function badgeButtonHtml({ tribe, dateIndex, label, isCurrent, title, icon }) {
        const iconImg = icon ? `<img src="${icon}" alt="${tribe}" class="allegiance-icon">` : '';
        return `
            <button type="button" class="allegiance-badge ${isCurrent ? 'is-current' : 'is-past'}"
                    data-tribe="${tribe}" data-date-index="${dateIndex}" title="${title}">
                ${iconImg}<span class="allegiance-date">${label}</span>
            </button>`;
    }

    function renderLegend(items) {
        $legend.html(items.map(([color, text]) =>
            `<div class="legend-item"><span class="legend-dot" style="background: ${color}"></span><span>${text}</span></div>`
        ).join(''));
    }

    function updateChrome() {
        $wrapper.attr('data-view', currentView);

        if (currentView === 'pn' && selectedPlayer) {
            $headerTitle.html(`&lsaquo; ${selectedPlayer.toUpperCase()}'S CIRCLE`);
            renderLegend([
                [same_tribe, 'Same homeland'],
                [other_tribe, 'Other homeland'],
                [unaligned, 'Unaligned']
            ]);

            const history = getPlayerHistory(selectedPlayer);
            const badges = !history.length
                ? '<div class="allegiance-empty">Unaligned</div>'
                : history.map(s => {
                    const start = formatShortDate(s.startDate), end = formatShortDate(s.endDate);
                    const label = s.isCurrent ? `since ${start}` : (s.startDate === s.endDate ? start : `${start} &ndash; ${end}`);
                    return badgeButtonHtml({
                        tribe: s.tribe,
                        dateIndex: s.startIndex,
                        label,
                        isCurrent: s.isCurrent,
                        title: `View ${s.tribe} Clearing ${start}`,
                        icon: config.tribes?.[s.tribe]?.icon
                    });
                }).join('');
            $ledger.html(`<div class="allegiance-ledger-title">Allegiances</div>${badges}`);
            return;
        }

        if (currentView === 'hn' && activeTribe) {
            $headerTitle.html(`&lsaquo; ${activeTribe.toUpperCase()} CLEARING`);
            renderLegend([
                [same_tribe, 'Partisan'],
                [`color-mix(in srgb, ${same_tribe} 50%, ${other_tribe})`, 'Squire'],
                [other_tribe, 'Friend']
            ]);

            const life = getTribeLifespan(activeTribe);
            if (!life) return $ledger.empty();

            const badges = life.milestones.map(m => badgeButtonHtml({
                tribe: activeTribe,
                dateIndex: m.idx,
                label: m.label,
                isCurrent: currentIndex === m.idx,
                title: m.title
            })).join('');
            $ledger.html(`<div class="allegiance-ledger-title">Chronicle</div>${badges}`);
            return;
        }

        $headerTitle.text('HOMELANDS MAP');
        $legend.empty();
        $ledger.empty();
    }

    // --- Graph Data Builders ---
    function buildGraphData(snapshot) {
        const nodes = [], links = [];

        if (currentView === 'pn') {
            const allKeys = Object.keys(constellations);
            if (!allKeys.length) {
                nodes.push({ id: 'placeholder', type: 'tribe', label: 'No player data', count: 0, radius: 40 });
                return { nodes, links };
            }
            const found = findPlayer(selectedPlayer || $searchInput.val()) || { name: allKeys[0], data: constellations[allKeys[0]] };
            selectedPlayer = found.name;

            const centerTribe = normalizeTribe(found.data.tribe);
            const games = found.data.games || 0;
            const partners = [...(found.data.partners || [])].sort((a, b) => b[1] - a[1]);
            const total = partners.length;
            const maxW = total ? partners[0][1] : 1;
            const minW = total ? partners[total - 1][1] : 1;
            const maxPRad = total ? partnerRadius(maxW) : 8;
            const cRad = centerRadius(games, maxPRad);

            nodes.push({
                id: selectedPlayer,
                type: 'ego-center',
                name: selectedPlayer,
                status: `${games} ${games === 1 ? 'game' : 'games'}`,
                radius: cRad,
                color: networkColor(centerTribe, centerTribe, true)
            });

            const minDist = cRad + maxPRad + 16;
            const maxDist = Math.min(198, Math.max(minDist + 40, 85 + total * 5.5));
            const sMax = Math.sqrt(maxW), sMin = Math.sqrt(minW);

            partners.forEach(([pName, weight], idx) => {
                const id = `partner_${pName}`;
                const wNorm = sMax > sMin ? (sMax - Math.sqrt(weight)) / (sMax - sMin) : 0;
                const rNorm = total > 1 ? idx / (total - 1) : 0;
                const t = sMax > sMin ? (0.6 * wNorm + 0.4 * rNorm) : rNorm;
                const color = networkColor(centerTribe, getPlayerTribe(pName), false);

                nodes.push({
                    id,
                    type: 'ego-partner',
                    name: pName,
                    status: `${weight} ${weight === 1 ? 'game' : 'games'}`,
                    color,
                    radius: partnerRadius(weight),
                    dist: minDist + t * (maxDist - minDist),
                    angle: idx * GOLDEN_ANGLE - Math.PI / 2
                });
                links.push({ source: selectedPlayer, target: id, type: 'ego-link', color });
            });
            return { nodes, links };
        }

        if (currentView === 'hm' || !activeTribe) {
            const activeTribes = Object.keys(snapshot || {}).filter(t => snapshot[t]?.length > 0);
            activeTribes.forEach((t, idx) => {
                const count = snapshot[t].length;
                nodes.push({
                    id: t,
                    type: 'tribe',
                    label: t,
                    count,
                    radius: tribeRadius(count),
                    spawnAngle: (2 * Math.PI * idx) / (activeTribes.length || 1) - Math.PI / 2
                });
            });
            for (let i = 0; i < activeTribes.length; i++) {
                for (let j = i + 1; j < activeTribes.length; j++) {
                    links.push({ source: activeTribes[i], target: activeTribes[j], type: 'inter-tribe' });
                }
            }
            return { nodes, links };
        }

        const members = [...(snapshot[activeTribe] || [])].sort((a, b) => b[2] - a[2]);
        const count = members.length;
        const maxWeight = count ? members[0][2] : 1;

        nodes.push({ id: activeTribe, type: 'tribe', label: activeTribe, count, radius: tribeRadius(count) });

        members.forEach(([pName, fidelity, weight], idx) => {
            const ringKey = idx < Math.max(1, Math.floor(count * 0.25)) ? 'core'
                          : idx < Math.max(2, Math.floor(count * 0.65)) ? 'mid' : 'outer';
            const slot = (2 * Math.PI) / (count || 1);
            const angle = TIER_PHASE[ringKey] * 2 * Math.PI + slot * idx + (nameJitter(pName) - 0.5) * slot * 0.6 - Math.PI / 2;
            const color = fidelityColor(fidelity);
            const id = `player_${pName}`;

            nodes.push({
                id,
                type: 'player',
                name: pName,
                status: `${Math.round(fidelity)}%`,
                color,
                radius: 8 + (maxWeight > 0 ? weight / maxWeight : 0) * 14,
                dist: ringKey === 'core' ? 75 : ringKey === 'mid' ? 125 : 185,
                angle
            });
            links.push({ source: activeTribe, target: id, type: 'constellation-link', color });
        });

        return { nodes, links };
    }

    // --- D3 Rendering & Force Simulation ---
    function renderGraph(snapshot) {
        if (typeof d3 === 'undefined') return;

        const svg = d3.select('#tribeMapSvg');
        const container = document.getElementById('tribeMapContainer');
        const width = container?.clientWidth || 800;
        const height = container?.clientHeight || 450;
        const originX = width / 2, originY = height / 2;
        const duration = 450, easeFn = d3.easeCubicOut;

        const { nodes: newNodes, links: newLinks } = buildGraphData(snapshot);
        updateChrome();

        const prevMap = new Map(simulation ? simulation.nodes().map(d => [d.id, d]) : []);
        const topologyChanged = lastRenderedView !== currentView ||
            newNodes.length !== prevMap.size ||
            newNodes.some(n => !prevMap.has(n.id));
        lastRenderedView = currentView;

        const hmRingRadius = newNodes.length >= 3
            ? Math.min(width, height) * (newNodes.length >= 5 ? 0.35 : 0.30)
            : 80;

        newNodes.forEach(d => {
            const prev = prevMap.get(d.id);
            if (prev) {
                Object.assign(d, {
                    x: prev.x, y: prev.y,
                    vx: (prev.vx || 0) * 0.3, vy: (prev.vy || 0) * 0.3,
                    currentRadius: prev.currentRadius ?? prev.radius
                });
            } else {
                d.currentRadius = 0;
                if (d.dist != null) {
                    d.x = originX + d.dist * Math.cos(d.angle || 0);
                    d.y = originY + d.dist * Math.sin(d.angle || 0);
                } else if (d.spawnAngle != null && currentView === 'hm') {
                    d.x = originX + hmRingRadius * Math.cos(d.spawnAngle);
                    d.y = originY + hmRingRadius * Math.sin(d.spawnAngle);
                } else {
                    d.x = originX + (Math.random() - 0.5) * 10;
                    d.y = originY + (Math.random() - 0.5) * 10;
                }
            }
        });

        const drag = d3.drag()
            .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; });

        const link = svg.select('g.links-layer').selectAll('line')
            .data(newLinks, d => `${d.source.id || d.source}-${d.target.id || d.target}`)
            .join(
                enter => enter.append('line').style('opacity', 0),
                update => update,
                exit => exit.transition().duration(duration * 0.7).ease(easeFn).style('opacity', 0).remove()
            )
            .attr('class', d => `link ${d.type || 'constellation-link'}`)
            .style('--node-color', d => d.color || null);

        link.transition().duration(duration).ease(easeFn).style('opacity', 1);

        const node = svg.select('g.nodes-layer').selectAll('g.node-group')
            .data(newNodes, d => d.id)
            .join(
                enter => {
                    const g = enter.append('g')
                        .style('opacity', 0)
                        .attr('transform', d => `translate(${d.x},${d.y})`)
                        .call(drag);

                    g.append('circle').attr('class', 'node-circle').attr('r', 0);
                    g.append('image').attr('class', 'node-icon').attr('width', 0).attr('height', 0);

                    const countTxt = g.append('text').attr('class', 'count-text');
                    countTxt.append('tspan').attr('class', 'num-span').attr('x', 0).attr('dy', '0');
                    countTxt.append('tspan').attr('class', 'lbl-span').attr('x', 0).attr('dy', '1.05em');

                    const playerLbl = g.append('text').attr('class', 'player-label');
                    playerLbl.append('tspan').attr('class', 'player-name-tspan').attr('x', 0);
                    playerLbl.append('tspan').attr('class', 'player-status-tspan').attr('x', 0).attr('dy', '1.15em');
                    return g;
                },
                update => update,
                exit => {
                    exit.select('.node-circle').transition().duration(duration).ease(easeFn).attr('r', 0);
                    exit.select('.node-icon').transition().duration(duration).ease(easeFn).attr('width', 0).attr('height', 0).attr('x', 0).attr('y', 0);
                    return exit.transition().duration(duration).ease(easeFn).style('opacity', 0).remove();
                }
            )
            .attr('class', d => `node-group type-${d.type} ${activeTribe === d.id ? 'is-selected' : ''}`)
            .style('--node-color', d => d.color || null);

        node.transition().duration(duration).ease(easeFn).style('opacity', 1);

        node.each(function (d) {
            const g = d3.select(this);
            const startR = d.currentRadius ?? 0;

            g.select('.node-circle').transition().duration(duration).ease(easeFn)
                .attrTween('r', () => {
                    const interp = d3.interpolateNumber(startR, d.radius);
                    return t => (d.currentRadius = interp(t));
                });

            if (d.type === 'tribe') {
                const iconPath = config.tribes?.[d.id]?.icon || '';
                const size = Math.max(22, d.radius * 0.65);
                g.select('.node-icon')
                    .attr('href', iconPath)
                    .transition().duration(duration).ease(easeFn)
                    .attr('width', size).attr('height', size)
                    .attr('x', -size / 2).attr('y', -size / 2 - 13);
                g.select('.count-text')
                    .transition().duration(duration).ease(easeFn)
                    .attr('transform', `translate(0, ${size / 2 - 1})`);
                g.select('.num-span').text(d.count);
                g.select('.lbl-span').text(d.count === 1 ? ' denizen' : ' denizens');
            } else {
                g.select('.player-name-tspan')
                    .attr('dy', d.type === 'ego-center' ? '-0.2em' : '0.3em')
                    .text(d.name);
                g.select('.player-status-tspan').text(d.status || '');
            }
        });

        node.on('click', (event, d) => {
            if (event.defaultPrevented) return;
            if (d.type === 'tribe' && currentView !== 'pn') {
                activeTribe = activeTribe === d.id ? null : d.id;
                currentView = activeTribe ? 'hn' : 'hm';
                updateView(dates[currentIndex]);
            } else if ((d.type === 'player' || d.type === 'ego-partner') && currentView === 'pn') {
                selectedPlayer = d.name;
                $searchInput.val(selectedPlayer);
                updateView(dates[dates.length - 1]);
            }
        }).on('dblclick', (event, d) => {
            if (event.defaultPrevented || (d.type !== 'player' && d.type !== 'ego-partner')) return;
            selectedPlayer = d.name;
            currentView = 'pn';
            $searchInput.val(selectedPlayer);
            updateView(dates[dates.length - 1]);
        });

        if (!simulation) {
            simulation = d3.forceSimulation().alphaDecay(0.045).velocityDecay(0.35);
        }
        const linkForce = d3.forceLink().id(d => d.id);

        if (currentView === 'hm') {
            const n = newNodes.length;
            simulation
                .force('center', d3.forceCenter(originX, originY).strength(0.1))
                .force('x', d3.forceX(originX).strength(0.04))
                .force('y', d3.forceY(originY).strength(0.06))
                .force('radial', n >= 3 ? d3.forceRadial(hmRingRadius, originX, originY).strength(0.55) : null)
                .force('link', linkForce.distance(d => (d.source.radius || 40) + (d.target.radius || 40) + 85).strength(n >= 4 ? 0.15 : 0.35))
                .force('charge', d3.forceManyBody().strength(-420))
                .force('collision', d3.forceCollide().radius(d => d.radius + 22).iterations(2));
        } else {
            const isHub = d => d.type === 'tribe' || d.type === 'ego-center';
            simulation
                .force('center', null)
                .force('radial', null)
                .force('link', linkForce.distance(0).strength(0))
                .force('charge', d3.forceManyBody().strength(d => isHub(d) ? 0 : -25))
                .force('x', d3.forceX(originX).strength(d => isHub(d) ? 0.3 : 0))
                .force('y', d3.forceY(originY).strength(d => isHub(d) ? 0.3 : 0))
                .force('collision', d3.forceCollide().radius(d => d.radius + 6));
        }

        simulation.nodes(newNodes);
        simulation.force('link').links(newLinks);
        simulation.alpha(topologyChanged ? 0.45 : 0.18).restart();

        simulation.on('tick', () => {
            if (currentView !== 'hm') {
                const hub = newNodes.find(n => n.type === 'tribe' || n.type === 'ego-center');
                const pull = currentView === 'pn' ? 0.15 : 0.12;
                if (hub) {
                    newNodes.forEach(d => {
                        if (d === hub || d.dist == null || d.fx != null) return;
                        const dx = d.x - hub.x, dy = d.y - hub.y;
                        const r = Math.hypot(dx, dy) || 1e-6;
                        const k = ((d.dist - r) / r) * pull;
                        d.x += dx * k;
                        d.y += dy * k;
                    });
                }
            }

            newNodes.forEach(d => {
                const pad = (d.currentRadius ?? d.radius) + 4;
                d.x = Math.max(pad, Math.min(width - pad, d.x));
                d.y = Math.max(pad, Math.min(height - pad, d.y));
            });

            link.each(function (d) {
                const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
                const dist = Math.hypot(dx, dy) || 1;
                const rS = d.source.currentRadius ?? d.source.radius ?? 0;
                const rT = d.target.currentRadius ?? d.target.radius ?? 0;
                const obstructed = d.type === 'inter-tribe' && newNodes.length >= 3 && newNodes.some(o =>
                    o.id !== d.source.id && o.id !== d.target.id &&
                    distToSegment(o.x, o.y, d.source.x, d.source.y, d.target.x, d.target.y) < (o.currentRadius ?? o.radius ?? 32) + 10
                );

                d3.select(this)
                    .attr('x1', d.source.x + (dx / dist) * rS)
                    .attr('y1', d.source.y + (dy / dist) * rS)
                    .attr('x2', d.target.x - (dx / dist) * rT)
                    .attr('y2', d.target.y - (dy / dist) * rT)
                    .attr('stroke-opacity', obstructed ? 0 : null);
            });

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
    }

    // --- Timeline & Navigation Controls ---
    function updateView(selectedDate) {
        let minIdx = 0, maxIdx = dates.length - 1;

        if (currentView === 'pn') {
            selectedDate = dates[maxIdx];
        } else if (currentView === 'hn' && activeTribe) {
            const life = getTribeLifespan(activeTribe);
            if (!life) {
                currentView = 'hm';
                activeTribe = null;
            } else {
                minIdx = life.firstIndex;
                maxIdx = life.lastIndex;
                if (!life.activeIndices.includes(currentIndex)) {
                    currentIndex = life.activeIndices.reduce((a, b) =>
                        Math.abs(b - currentIndex) < Math.abs(a - currentIndex) ? b : a
                    );
                    selectedDate = dates[currentIndex];
                }
            }
        }

        $datePicker.attr({ min: dates[minIdx], max: dates[maxIdx] }).val(selectedDate);
        if (snapshots[selectedDate]) renderGraph(snapshots[selectedDate]);

        const isPN = currentView === 'pn';
        $prevBtn.add($earliestBtn).prop('disabled', isPN || currentIndex <= minIdx);
        $nextBtn.add($latestBtn).prop('disabled', isPN || currentIndex >= maxIdx);
    }

    function setDateByIndex(idx) {
        const life = currentView === 'hn' ? getTribeLifespan(activeTribe) : null;
        const min = life ? life.firstIndex : 0;
        const max = life ? life.lastIndex : dates.length - 1;
        currentIndex = Math.max(min, Math.min(max, idx));
        updateView(dates[currentIndex]);
    }

    function stepDate(dir) {
        const life = currentView === 'hn' ? getTribeLifespan(activeTribe) : null;
        if (life) {
            const pos = life.activeIndices.indexOf(currentIndex);
            if (pos !== -1 && life.activeIndices[pos + dir] !== undefined) {
                setDateByIndex(life.activeIndices[pos + dir]);
            }
            return;
        }
        setDateByIndex(currentIndex + dir);
    }

    // --- Event Listeners ---
    $ledger.on('click', '.allegiance-badge', function (e) {
        e.stopPropagation();
        const tribe = $(this).data('tribe');
        const idx = parseInt($(this).data('date-index'), 10);
        if (!tribe || isNaN(idx)) return;
        currentView = 'hn';
        activeTribe = tribe;
        setDateByIndex(idx);
    });

    $searchInput.on('input change', function () {
        const q = $(this).val().trim();
        if (!q) {
            currentView = 'hm';
            activeTribe = null;
            selectedPlayer = null;
            updateView(dates[currentIndex]);
        } else {
            const found = findPlayer(q);
            if (found) {
                selectedPlayer = found.name;
                currentView = 'pn';
                updateView(dates[dates.length - 1]);
            }
        }
    });

    $headerTitle.on('click', () => {
        currentView = 'hm';
        activeTribe = null;
        selectedPlayer = null;
        if ($searchInput.val()) $searchInput.val('').trigger('change');
        else updateView(dates[currentIndex]);
    });

    $prevBtn.on('click', () => stepDate(-1));
    $nextBtn.on('click', () => stepDate(1));
    $earliestBtn.on('click', () => setDateByIndex(0));
    $latestBtn.on('click', () => setDateByIndex(dates.length - 1));

    $datePicker.on('change', function () {
        const idx = dates.findIndex(d => d >= $(this).val());
        setDateByIndex(idx !== -1 ? idx : dates.length - 1);
    });

    $(window).on('resize', () => { if (dates[currentIndex]) updateView(dates[currentIndex]); });

    setDateByIndex(currentIndex);
});
