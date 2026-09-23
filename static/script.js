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
    const $datePicker =$('#datePicker').attr({ min: dates[0], max: dates[dates.length - 1] });
    const $prevBtn =$('#prevDateBtn');
    const $nextBtn =$('#nextDateBtn');
    const $earliestBtn =$('#earliestDateBtn');
    const $latestBtn =$('#latestDateBtn');

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
    function buildGraphData(snapshot, width, height) {
        const activeTribes = snapshot.active_tribes || [];
        const tribeLayout = snapshot.tribe_layout || {};
        const playersMap = new Map((snapshot.players || []).map(p => [p.name, p]));
        const nodes = [];
        const links = [];

        if (!activeTribeFilter) {
            // Vue Globale
            activeTribes.forEach(t => {
                const count = snapshot.summary?.[t] || 0;
                nodes.push({
                    id: t,
                    type: 'tribe',
                    label: snapshot.tribe_labels?.[t] || t,
                    count: count,
                    radius: Math.max(30, 22 + Math.sqrt(count) * 10)
                });
            });

            for (let i = 0; i < activeTribes.length; i++) {
                for (let j = i + 1; j < activeTribes.length; j++) {
                    const t1 = activeTribes[i];
                    const t2 = activeTribes[j];
                    let totalAffinity = 0;
                    let count = 0;

                    (snapshot.players || []).forEach(p => {
                        if (p.main_tribe === t1 && p.scores?.[t2]) {
                            totalAffinity += p.scores[t2].pct;
                            count++;
                        } else if (p.main_tribe === t2 && p.scores?.[t1]) {
                            totalAffinity += p.scores[t1].pct;
                            count++;
                        }
                    });

                    const avg = count > 0 ? totalAffinity / count : 0;
                    if (avg > 2) {
                        links.push({ source: t1, target: t2, value: avg, type: 'inter-tribe' });
                    }
                }
            }
        } else {
            // Vue Constellation par tribu
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
                radius: Math.max(36, 26 + Math.sqrt(count) * 10)
            });

            // Récupération de TOUS les membres de la tribu
            const allTribePlayers = (snapshot.players || []).filter(p => p.main_tribe === tribe);

            // 1. Préparation des 3 listes par rôle
            const pillarsList = allTribePlayers
                .filter(p => pillarsSet.has(p.name))
                .map(p => ({ name: p.name, role: 'pillar', isPillar: true, isSatellite: false, dist: 75, radius: 24 }));

            const satellitesList = allTribePlayers
                .filter(p => satellitesSet.has(p.name) && !pillarsSet.has(p.name))
                .map(p => ({ name: p.name, role: 'satellite', isPillar: false, isSatellite: true, dist: 110, radius: 14 }));

            const othersList = allTribePlayers
                .filter(p => !pillarsSet.has(p.name) && !satellitesSet.has(p.name))
                .map(p => ({ name: p.name, role: 'member', isPillar: false, isSatellite: false, dist: 145, radius: 8 }));

            // 2. Entrelacement (Round-Robin) pour mélanger les tailles sur tout le tour du cercle
            const placementList = [];
            const maxLen = Math.max(pillarsList.length, satellitesList.length, othersList.length);

            for (let i = 0; i < maxLen; i++) {
                if (i < pillarsList.length) placementList.push(pillarsList[i]);
                if (i < satellitesList.length) placementList.push(satellitesList[i]);
                if (i < othersList.length) placementList.push(othersList[i]);
            }

            // 3. Distribution angulaire globale sur 360°
            const totalMembers = placementList.length || 1;

            placementList.forEach((item, idx) => {
                const pData = playersMap.get(item.name);
                const scoreObj = pData?.scores?.[tribe];

                // Distribution régulière autour du cadran
                const angle = (2 * Math.PI * idx / totalMembers) - (Math.PI / 2);
                const playerId = `player_${item.name}`;

                nodes.push({
                    id: playerId,
                    type: 'player',
                    name: item.name,
                    role: item.role,
                    isPillar: item.isPillar,
                    isSatellite: item.isSatellite,
                    pct: scoreObj?.pct || 0,
                    status: scoreObj?.status || null,
                    color: getBadgeColor(scoreObj?.status),
                    radius: item.radius,
                    targetX: width / 2 + item.dist * Math.cos(angle),
                    targetY: height / 2 + item.dist * Math.sin(angle)
                });

                links.push({
                    source: tribe,
                    target: playerId,
                    type: 'constellation-link',
                    isPillar: item.isPillar,
                    isSatellite: item.isSatellite,
                    role: item.role
                });
            });
        }
		
		nodes.sort((a, b) => {
            const weights = { 'member': 1, 'satellite': 2, 'pillar': 3, 'tribe': 4 };
            return (weights[a.role] || 0) - (weights[b.role] || 0);
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

        const { nodes: newNodes, links: newLinks } = buildGraphData(snapshot, width, height);

        // Maintien des positions lors des transitions
        const prevNodesMap = new Map(simulation ? simulation.nodes().map(d => [d.id, d]) : []);
        let originX = width / 2, originY = height / 2;

        if (activeTribeFilter && prevNodesMap.has(activeTribeFilter)) {
            const prevTribe = prevNodesMap.get(activeTribeFilter);
            originX = prevTribe.x;
            originY = prevTribe.y;
        }

        newNodes.forEach(d => {
            if (prevNodesMap.has(d.id)) {
                const prev = prevNodesMap.get(d.id);
                d.x = prev.x; d.y = prev.y;
            } else {
                d.x = originX; d.y = originY;
            }
        });

        const drag = d3.drag()
            .on("start", (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on("end", (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; });

        // --- Liens ---
		const link = linkEnter.merge(linkSel);

		link.attr("class", d => `link ${d.type} ${d.isPillar ? 'is-pillar' : ''} ${d.isSatellite ? 'is-satellite' : ''}`)
			.style("stroke-dasharray", "none") // Force des lignes pleines et continues
			.transition().duration(duration)
			.attr("stroke-width", d => d.type === 'inter-tribe' ? Math.max(1, d.value / 5) : null);

        // --- Nœuds ---
        const nodeSel = svg.select("g.nodes-layer").selectAll("g.node-group")
            .data(newNodes, d => d.id);

        nodeSel.exit().transition().duration(duration).style("opacity", 0).remove();

        const nodeEnter = nodeSel.enter().append("g")
            .call(drag);

        nodeEnter.append("circle").attr("class", "node-circle");
        nodeEnter.append("image").attr("class", "node-icon");

        const textGroup = nodeEnter.append("text").attr("class", "count-text");
        textGroup.append("tspan")
            .attr("class", "num-span")
            .attr("x", 0)
            .attr("dy", "0");
            
        textGroup.append("tspan")
            .attr("class", "lbl-span")
            .attr("x", 0)
            .attr("dy", "1.2em");

        nodeEnter.append("text").attr("class", "player-label");

        const node = nodeEnter.merge(nodeSel);

        // Application des classes dynamiques pour le styling CSS
        node.attr("class", d => `node-group type-${d.type} ${activeTribeFilter === d.id ? 'is-selected' : ''} ${d.isPillar ? 'is-pillar' : ''} ${d.isSatellite ? 'is-satellite' : ''} role-${d.role || 'none'}`)
            .style("--node-color", d => d.color || null)
            .transition().duration(duration).style("opacity", 1);

        node.each(function (d) {
            const g = d3.select(this);

            if (d.type === 'tribe') {
                const iconPath = config.tribes?.[d.id]?.icon || '';
                const iconSize = Math.max(24, d.radius * 0.7);

                g.select(".node-circle").transition().duration(duration).attr("r", d.radius);
                g.select(".node-icon")
                    .attr("href", iconPath).attr("xlink:href", iconPath)
                    .attr("width", iconSize).attr("height", iconSize)
                    .attr("x", -iconSize / 2).attr("y", -iconSize / 2 - 6);

                g.select(".count-text").attr("transform", `translate(0, ${iconSize / 2 + 8})`);
                g.select(".num-span").text(d.count);
                g.select(".lbl-span").text(" members");
            } else {
                g.select(".node-circle").transition().duration(duration).attr("r", d.radius);

                let labelClass = "player-label member-label";
                if (d.isPillar) {
                    labelClass = "player-label pillar-label";
                } else if (d.isSatellite) {
                    labelClass = "player-label satellite-label";
                }

                g.select(".player-label")
                    .text(d.name)
                    .attr("class", labelClass);
            }
        });

        node.on("click", (event, d) => {
            if (event.defaultPrevented || d.type !== 'tribe') return;
            activeTribeFilter = (activeTribeFilter === d.id) ? null : d.id;
            updateView(dates[currentIndex]);
        });

        // --- Simulation Physique ---
        if (!simulation) simulation = d3.forceSimulation();
        const linkForce = d3.forceLink().id(d => d.id);

        if (!activeTribeFilter) {
            simulation
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("link", linkForce.distance(145))
                .force("charge", d3.forceManyBody().strength(-320))
                .force("x", d3.forceX(width / 2).strength(0.08))
                .force("y", d3.forceY(height / 2).strength(0.08))
                .force("collision", d3.forceCollide().radius(d => d.radius + 15));
        } else {
            simulation
                .force("center", null)
                .force("link", linkForce.distance(d => {
                    if (d.isPillar) return 70;
                    if (d.isSatellite) return 110;
                    return 140;
                }))
                .force("charge", d3.forceManyBody().strength(-40))
                .force("x", d3.forceX(d => (d.type === 'tribe' && d.id === activeTribeFilter) ? width / 2 : (d.targetX || width / 2)).strength(d => (d.type === 'tribe' && d.id === activeTribeFilter) ? 0.15 : 0.3))
                .force("y", d3.forceY(d => (d.type === 'tribe' && d.id === activeTribeFilter) ? height / 2 : (d.targetY || height / 2)).strength(d => (d.type === 'tribe' && d.id === activeTribeFilter) ? 0.15 : 0.3))
                .force("collision", d3.forceCollide().radius(d => d.radius + 8));
        }

        simulation.nodes(newNodes);
        simulation.force("link").links(newLinks);
        simulation.alpha(0.6).restart();

        simulation.on("tick", () => {
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
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

        $prevBtn.prop('disabled', currentIndex <= 0);$nextBtn.prop('disabled', currentIndex >= dates.length - 1);
    }

    function setDateByIndex(index) {
        if (index >= 0 && index < dates.length) {
            currentIndex = index;
            updateView(dates[currentIndex]);
        }
    }

    // Écouteurs d'événements UI
    $prevBtn.on('click', () => setDateByIndex(currentIndex - 1));$nextBtn.on('click', () => setDateByIndex(currentIndex + 1));
    $earliestBtn.on('click', () => setDateByIndex(0));$latestBtn.on('click', () => setDateByIndex(dates.length - 1));

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
