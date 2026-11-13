/* =========================================================================
   ROOTELO - JAVASCRIPT
   Table of Contents:
   0.  General Helpers
   1.  Dynamic Scroll
   2.  Double-tap
   3.  Tier Modal
   4.  Data Tables
   5.  Chart
   6.  Dynamic Trends
   7.  Narrative Journey
   8.  Global Player Search
   9.  Match Simulator Engine
   10. Homelands Map & Player Network Engine
   
   --- EASTER EGGS ---
   11. Secrets Engine
   12. Nut & Berry
   13. Visitor Recognition
   ========================================================================= */
   
/* =========================================================================
   --- 0. GENERAL HELPERS ---
   ========================================================================= */
   
window.getSeasonPage = function(base) {
    const match = window.location.pathname.match(/_([^/.]+)\.html$/i);
    return `${base}${match ? '_' + match[1] : ''}.html`;
};
   
/* =========================================================================
   --- 1. DYNAMIC SCROLL ---
   ========================================================================= */

let touchStartY = 0;
let lastScrollY = window.scrollY;

window.addEventListener('touchstart', (e) => {
    touchStartY = e.touches[0].clientY; 
}, { passive: true });

window.addEventListener('touchmove', (e) => {
    const isMobile = window.innerWidth < 1100;
    if (!isMobile) return;

    const currentY = e.touches[0].clientY;
    const hasClass = document.body.classList.contains('is-at-bottom');

    if (hasClass && (currentY - touchStartY) > 40) {
        document.body.classList.remove('is-at-bottom');
        return;
    }

    const windowHeight = window.innerHeight;
    const docHeight = document.documentElement.scrollHeight;
    const isAtBottom = Math.ceil(windowHeight + window.scrollY) >= (docHeight - 15);

    if (isAtBottom && !hasClass && (touchStartY - currentY) > 70) {
        document.body.classList.add('is-at-bottom');
    }
}, { passive: true });

window.addEventListener('scroll', () => {
    const currentScrollY = window.scrollY;
    const isMobile = window.innerWidth < 1100;

    document.body.style.setProperty('--scroll', currentScrollY);

    if (currentScrollY > 30) {
        document.body.classList.add('is-scrolled');
    } else {
        document.body.classList.remove('is-scrolled');
    }

    if (isMobile && document.body.classList.contains('is-at-bottom')) {
        if (currentScrollY < lastScrollY - 10) {
            document.body.classList.remove('is-at-bottom');
        }
    }
    
    lastScrollY = currentScrollY;
}, { passive: true });

/* =========================================================================
   --- 2. DOUBLE-TAP ---
   ========================================================================= */
   
document.addEventListener("DOMContentLoaded", function() {
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || (window.matchMedia("(hover: none)").matches);

    if (isTouchDevice) {
        document.body.addEventListener('click', function(e) {
            const link = e.target.closest('.js-double-tap');

            if (!link) {
                document.querySelectorAll('.js-double-tap.expanded').forEach(l => l.classList.remove('expanded'));
                return;
            }

            if (!link.classList.contains('expanded')) {
                e.preventDefault();
                e.stopPropagation();

                document.querySelectorAll('.js-double-tap.expanded').forEach(l => l.classList.remove('expanded'));
                link.classList.add('expanded');
            } else {
                link.classList.remove('expanded');
            }
        }, true);
    }
});

/* =========================================================================
   --- 3. TIER MODAL ---
   ========================================================================= */
		
document.addEventListener('DOMContentLoaded', function() {
	const modal = document.getElementById('tierModal');
	const closeBtn = document.querySelector('.modal-close');

	const tierColors = CONFIG.colors;
	const tierIcons = CONFIG.icons;

	window.openTierModal = function(tier, playerName, clearing) {
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
		const modalFinal = document.getElementById('modalFinal');
		const supporterLeft = document.getElementById('modalSupporterLeft');
		const supporterRight = document.getElementById('modalSupporterRight');

		modalTitle.textContent = text.name;
		modalElo.textContent = playerName || text.elo || '';
		modalElo.style.color = color;
		modalIcon.src = icon;
		modalSubtitle.textContent = (tier === 'frog' && playerName) ? 'Homeland Herald' : (text.subtitle || '');
		modalText.textContent = text.desc;

		const isFrog = Boolean(tier === 'frog' && clearing);

        [supporterLeft, supporterRight].forEach(el => {
            if (!el) return;
            el.classList.toggle('is-visible', isFrog);
            if (isFrog) {
                const key = clearing.toLowerCase();
                el.href = `${PATH_PREFIX}${getSeasonPage('network')}?clearing=${key}#view`;
                el.querySelector('img').src = `${PATH_PREFIX}assets/items/${key}.png`;
            }
        });

		if (modalFinal) {
			modalFinal.innerHTML = text.final || '';
		}
		
		if (typeof modalCrown !== 'undefined' && modalCrown) {
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

	if ($('#leaderboard').length > 0) {
		const pageName = window.location.pathname.split('/').pop() || '';
		let showAllPlayers = !pageName.includes('_'); 
		let savedClassicState = showAllPlayers;

		$('#tierFilterCheckbox').prop('checked', showAllPlayers);

		const isFrogActive = sessionStorage.getItem('spotFrogs') === 'true';
		if (isFrogActive) {
			$('#spotFrogsCheckbox').prop('checked', true);
			$('body').addClass('homelands-mode');
			$('#leaderboard').addClass('frogs-mode');
			showAllPlayers = false;
			$('#tierFilterCheckbox').prop('checked', false);
		}
		
		$.extend($.fn.dataTable.ext.type.order, { 
			"rank-pre": function (d) { 
				if (d === "♔") return 0; 
				if (d === "-" || d === "–" || d === "—") return 9999;
				return parseInt(d); 
			} 
		});

		$.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
			if (settings.nTable.id !== 'leaderboard') return true;
			const rowNode = settings.aoData[dataIndex].nTr;
			if (!rowNode) return true;

			const isFrogMode = $('#spotFrogsCheckbox').is(':checked');

			if (isFrogMode) {
				return showAllPlayers || rowNode.dataset.settler === 'true';
			}

			return showAllPlayers || rowNode.dataset.tier !== 'unassigned';
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

		$(document).on('change', '#spotFrogsCheckbox', function() {
			const isFrogMode = $(this).is(':checked');
			sessionStorage.setItem('spotFrogs', isFrogMode ? 'true' : 'false');

			$('body').toggleClass('homelands-mode', isFrogMode);
			$('#leaderboard').toggleClass('frogs-mode', isFrogMode);

			if (isFrogMode) {
				savedClassicState = $('#tierFilterCheckbox').is(':checked');
				showAllPlayers = false;
				$('#tierFilterCheckbox').prop('checked', false);
			} else {
				showAllPlayers = savedClassicState;
				$('#tierFilterCheckbox').prop('checked', savedClassicState);
			}

			$('#leaderboard').DataTable().draw();
		});
	}

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

$(document).on('dblclick', '.player-name-cell', function() {
    const playerName = $(this).text().trim();
    if (!playerName) return;

    localStorage.setItem('selectedPlayer', playerName);
    window.location.href = `${getSeasonPage('trends')}#view`;
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
	
    const nodeCenter = document.getElementById('nodeCenter');
    if (nodeCenter) {
        nodeCenter.setAttribute('data-player', playerName || '');
    }
    
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

window.goToPlayerCircle = function(element) {
    const input = document.getElementById('playerName');
    const playerName = (element && element.getAttribute('data-player')) || 
                       (input ? input.value.trim() : '') || 
                       localStorage.getItem('selectedPlayer');

    if (!playerName) return;

    localStorage.setItem('selectedPlayer', playerName);
    window.location.href = `${getSeasonPage('network')}?player=${encodeURIComponent(playerName)}#view`;
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
   --- 10. HOMELANDS MAP & PLAYER NETWORK ENGINE ---
   ========================================================================= */

$(document).ready(function () {
    const config = window.NETWORK_CONFIG || {};
    const rawConstellations = window.PLAYER_CONSTELLATIONS || {};
    const constellations = rawConstellations.players || rawConstellations;
    const { same_tribe, other_tribe, unaligned } = config.colors || {};

    const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
    const TIER_PHASE = { core: 0, mid: 0.22, outer: 0.47 };

    const normalizeTribe = t => (!t || t === '-' || t === 'UNALIGNED') ? null : t;
    const getPlayerTribe = name => normalizeTribe(constellations[name]?.tribe);
    const tribeRadius = count => Math.max(32, 24 + Math.sqrt(count || 0) * 10);
    const partnerRadius = games => Math.min(24, 6 + Math.sqrt(Math.max(1, games)) * 3);
    const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

    const fidelityColor = fidelity => {
        const pct = Math.round(Math.max(0, Math.min(1, ((Number(fidelity) || 0) - 35) / 60)) * 100);
        return `color-mix(in srgb, ${same_tribe} ${pct}%, ${other_tribe})`;
    };

    const networkColor = (centerTribe, nodeTribe, isCenter) => {
        if (isCenter) return centerTribe ? same_tribe : unaligned;
        if (!nodeTribe) return unaligned;
        return centerTribe && nodeTribe === centerTribe ? same_tribe : other_tribe;
    };

    const nameJitter = name => {
        let h = 0;
        for (let i = 0; i < name.length; i++) h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0;
        return (h % 10000) / 10000;
    };

    const distToSegment = (px, py, x1, y1, x2, y2) => {
        const dx = x2 - x1, dy = y2 - y1, lenSq = dx * dx + dy * dy;
        if (!lenSq) return Math.hypot(px - x1, py - y1);
        const t = Math.max(0.05, Math.min(0.95, ((px - x1) * dx + (py - y1) * dy) / lenSq));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    };

    let currentView = 'hm';
    let activeTribe = null;
    let selectedPlayer = null;

    function buildGraphData(snapshot, view = currentView, tribe = activeTribe, pnOverride = null) {
        const nodes = [], links = [];

        if (view === 'pn') {
            const centerName = pnOverride ? pnOverride.name : selectedPlayer;
            const data = pnOverride || constellations[selectedPlayer];
            if (!data) return { nodes, links };

            const centerTribe = normalizeTribe(data.tribe);
            const partners = [...(data.partners || [])].sort((a, b) => b[1] - a[1]);
            const total = partners.length;
            const maxW = total ? partners[0][1] : 1;
            const minW = total ? partners[total - 1][1] : 1;
            const cRad = 34;

            nodes.push({
                id: centerName,
                type: 'ego-center',
                name: centerName,
                status: plural(data.games || 0, 'game'),
                radius: cRad,
                color: networkColor(centerTribe, centerTribe, true)
            });

            const minDist = cRad + (total ? partnerRadius(maxW) : 8) + 18;
            const maxDist = Math.min(180, Math.max(minDist + 40, 85 + total * 5));
            const sMax = Math.sqrt(maxW), sMin = Math.sqrt(minW);

            partners.forEach(([pName, weight, pTribeOverride], idx) => {
                const id = `partner_${pName}`;
                const wNorm = sMax > sMin ? (sMax - Math.sqrt(weight)) / (sMax - sMin) : 0;
                const rNorm = total > 1 ? idx / (total - 1) : 0;
                const t = sMax > sMin ? (0.6 * wNorm + 0.4 * rNorm) : rNorm;
                const pTribe = pTribeOverride !== undefined ? pTribeOverride : getPlayerTribe(pName);
                const color = networkColor(centerTribe, pTribe, false);

                nodes.push({
                    id,
                    type: 'ego-partner',
                    name: pName,
                    status: plural(weight, 'game'),
                    color,
                    radius: partnerRadius(weight),
                    dist: minDist + t * (maxDist - minDist),
                    angle: idx * GOLDEN_ANGLE - Math.PI / 2
                });
                links.push({ source: centerName, target: id, type: 'ego-link', color });
            });
            return { nodes, links };
        }

        if (view === 'hm' || !tribe) {
            const activeTribes = Object.keys(snapshot || {}).filter(t => snapshot[t]?.length > 0);
            activeTribes.forEach((t, idx) => {
                const count = snapshot[t].length;
                nodes.push({
                    id: t,
                    type: 'tribe',
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

        const members = [...(snapshot[tribe] || [])].sort((a, b) => b[2] - a[2]);
        const count = snapshot[tribe].displayCount || members.length;
        const maxWeight = members.length ? members[0][2] : 1;

        nodes.push({ id: tribe, type: 'tribe', count, radius: tribeRadius(count) });

        members.forEach(([pName, fidelity, weight, statusOverride], idx) => {
            const mLen = members.length;
            const ringKey = idx < Math.max(1, Math.floor(mLen * 0.25)) ? 'core'
                          : idx < Math.max(2, Math.floor(mLen * 0.65)) ? 'mid' : 'outer';
            const slot = (2 * Math.PI) / (mLen || 1);
            const angle = TIER_PHASE[ringKey] * 2 * Math.PI + slot * idx + (nameJitter(pName) - 0.5) * slot * 0.6 - Math.PI / 2;
            const color = fidelityColor(fidelity);
            const id = `player_${pName}`;

            nodes.push({
                id,
                type: 'player',
                name: pName,
                status: statusOverride || `${Math.round(fidelity)}%`,
                color,
                radius: 8 + (maxWeight > 0 ? weight / maxWeight : 0) * 14,
                dist: ringKey === 'core' ? 75 : ringKey === 'mid' ? 120 : 170,
                angle
            });
            links.push({ source: tribe, target: id, type: 'constellation-link', color });
        });

        return { nodes, links };
    }

    function mountSvgGraph(svgEl, view, newNodes, newLinks, simInstance, selectedTribeId, isInteractive = true) {
        if (typeof d3 === 'undefined' || !svgEl) return null;

        const svg = d3.select(svgEl);
        const width = svgEl.clientWidth || 480;
        const height = svgEl.clientHeight || 220;
        const isDesktop = window.innerWidth > 768;
        const originX = width / 2;
        const originY = height / 2 + (isInteractive && isDesktop && (view === 'hn' || view === 'pn') ? 16 : 0);

        const prevMap = new Map(simInstance ? simInstance.nodes().map(d => [d.id, d]) : []);
        const topologyChanged = !simInstance ||
            simInstance._lastView !== view ||
            newNodes.length !== prevMap.size ||
            newNodes.some(n => !prevMap.has(n.id));

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
                const angle = d.dist != null ? (d.angle || 0) : (d.spawnAngle != null && view === 'hm' ? d.spawnAngle : null);
                const dist = d.dist ?? (angle != null ? hmRingRadius : 0);
                d.x = originX + (angle != null ? dist * Math.cos(angle) : (Math.random() - 0.5) * 10);
                d.y = originY + (angle != null ? dist * Math.sin(angle) : (Math.random() - 0.5) * 10);
            }
        });

        if (!simInstance) {
            simInstance = d3.forceSimulation().alphaDecay(0.045).velocityDecay(0.35);
        }
        simInstance._lastView = view;

        const drag = d3.drag()
            .on('start', (e, d) => { if (!e.active) simInstance.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end', (e, d) => { if (!e.active) simInstance.alphaTarget(0); d.fx = null; d.fy = null; });

        const link = svg.select('g.links-layer').selectAll('line')
            .data(newLinks, d => `${d.source.id || d.source}-${d.target.id || d.target}`)
            .join(
                enter => enter.append('line').style('opacity', 0),
                update => update,
                exit => exit.style('opacity', 0).transition().duration(320).remove()
            )
            .attr('class', d => `link ${d.type || 'constellation-link'}`)
            .style('--node-color', d => d.color || null);

        const node = svg.select('g.nodes-layer').selectAll('g.node-group')
            .data(newNodes, d => d.id)
            .join(
                enter => {
                    const g = enter.append('g')
                        .style('opacity', 0)
                        .style('--r', '0px')
                        .attr('transform', d => `translate(${d.x},${d.y})`)
                        .call(drag);

                    g.append('circle').attr('class', 'node-circle');
                    g.append('image').attr('class', 'node-icon');

                    const countTxt = g.append('text').attr('class', 'count-text');
                    countTxt.append('tspan').attr('class', 'num-span').attr('x', 0);
                    countTxt.append('tspan').attr('class', 'lbl-span').attr('x', 0).attr('dy', '1.05em');

                    const playerLbl = g.append('text').attr('class', 'player-label');
                    playerLbl.append('tspan').attr('class', 'player-name-tspan').attr('x', 0).attr('dy', '0.32em');
                    playerLbl.append('tspan').attr('class', 'player-status-tspan').attr('x', 0).attr('dy', '1.15em');

                    const overlayLbl = g.append('text').attr('class', 'ego-overlay-label');
                    overlayLbl.append('tspan').attr('class', 'ego-overlay-action').attr('x', 0).attr('dy', '-0.2em').text('Click to see');
                    overlayLbl.append('tspan').attr('class', 'ego-overlay-action').attr('x', 0).attr('dy', '1.2em').text('the Journey');
                    return g;
                },
                update => update,
                exit => exit.style('--r', '0px').style('opacity', 0).transition().duration(450).remove()
            )
            .attr('class', d => [
                'node-group',
                `type-${d.type}`,
                isInteractive && d.type !== 'tribe' ? 'js-double-tap' : '',
                selectedTribeId === d.id ? 'is-selected' : ''
            ].filter(Boolean).join(' '))
            .style('--node-color', d => d.color || null);

        node.select('.node-icon').attr('href', d => d.type === 'tribe' ? (config.tribes?.[d.id]?.icon || '') : null);
        node.select('.num-span').text(d => d.count ?? '');
        node.select('.lbl-span').text(d => ` ${d.count === 1 ? 'denizen' : 'denizens'}`);
        node.select('.player-name-tspan').text(d => d.name || '');
        node.select('.player-status-tspan').text(d => d.status || '');

        requestAnimationFrame(() => {
            link.style('opacity', 1);
            node.style('--r', d => `${d.radius}px`).style('opacity', 1);
        });

        if (isInteractive) {
            node.on('click', (event, d) => {
                if (event.defaultPrevented) return;
                event.stopPropagation();

                if (d.type === 'tribe' && currentView !== 'pn') {
                    setView(activeTribe === d.id ? 'hm' : 'hn', { tribe: activeTribe === d.id ? null : d.id });
                } else if (d.type === 'player' || d.type === 'ego-partner') {
                    setView('pn', { player: d.name });
                } else if (d.type === 'ego-center' && d.name) {
                    localStorage.setItem('selectedPlayer', d.name);
                    window.location.href = `${getSeasonPage('trends')}?player=${encodeURIComponent(d.name)}#view`;
                }
            });

            svg.on('click', () => {
                if (currentView === 'hn') setView('hm');
            });
        }

        const linkForce = d3.forceLink().id(d => d.id);

        if (view === 'hm') {
            const n = newNodes.length;
            simInstance
                .force('center', d3.forceCenter(originX, originY).strength(0.1))
                .force('x', d3.forceX(originX).strength(0.04))
                .force('y', d3.forceY(originY).strength(0.06))
                .force('radial', n >= 3 ? d3.forceRadial(hmRingRadius, originX, originY).strength(0.55) : null)
                .force('link', linkForce.distance(d => (d.source.radius || 40) + (d.target.radius || 40) + 85).strength(n >= 4 ? 0.15 : 0.35))
                .force('charge', d3.forceManyBody().strength(-420))
                .force('collision', d3.forceCollide().radius(d => d.radius + 22).iterations(2));
        } else {
            const isHub = d => d.type === 'tribe' || d.type === 'ego-center';
            simInstance
                .force('center', null)
                .force('radial', null)
                .force('link', linkForce.distance(0).strength(0))
                .force('charge', d3.forceManyBody().strength(d => isHub(d) ? 0 : -25))
                .force('x', d3.forceX(originX).strength(d => isHub(d) ? 0.3 : 0))
                .force('y', d3.forceY(originY).strength(d => isHub(d) ? 0.3 : 0))
                .force('collision', d3.forceCollide().radius(d => d.radius + 6));
        }

        simInstance.nodes(newNodes);
        simInstance.force('link').links(newLinks);
        simInstance.alpha(topologyChanged ? 0.45 : 0.18).restart();

        simInstance.on('tick', () => {
            if (view !== 'hm') {
                const hub = newNodes.find(n => n.type === 'tribe' || n.type === 'ego-center');
                const pull = view === 'pn' ? 0.15 : 0.12;
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
                d.currentRadius += (d.radius - (d.currentRadius ?? d.radius)) * 0.2;
                const pad = d.currentRadius + 6;
                const topPad = (isInteractive && isDesktop && view !== 'hm')
                    ? Math.max(pad, 55 + d.currentRadius)
                    : pad;

                d.x = Math.max(pad, Math.min(width - pad, d.x));
                d.y = Math.max(topPad, Math.min(height - pad, d.y));
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
                    .style('stroke-opacity', obstructed ? 0 : null);
            });

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        return simInstance;
    }

    const guideSims = {};

    function renderGuideGraphs() {
        if (typeof d3 === 'undefined') return;
        const tribeKeys = Object.keys(config.tribes || {});
        const t1 = tribeKeys[6] || tribeKeys[0] || 'sword';
        const t2 = tribeKeys[3] || tribeKeys[1] || 'tea';

        const hmEl = document.getElementById('guideMapHm');
        if (hmEl) {
            const hmData = buildGraphData({ [t1]: Array(9), [t2]: Array(6) }, 'hm', null);
            guideSims.hm = mountSvgGraph(hmEl, 'hm', hmData.nodes, hmData.links, guideSims.hm, null, false);
        }

        const hnEl = document.getElementById('guideMapHn');
        if (hnEl) {
            const hnMembers = [['Partisan', 95, 5], ['Squire', 65, 8], ['Friend', 35, 12]];
            hnMembers.displayCount = 9;
            const hnData = buildGraphData({ [t1]: hnMembers }, 'hn', t1);
            guideSims.hn = mountSvgGraph(hnEl, 'hn', hnData.nodes, hnData.links, guideSims.hn, t1, false);
        }

        const pnEl = document.getElementById('guideMapPn');
        if (pnEl) {
            const pnData = buildGraphData(null, 'pn', null, {
                name: 'Denizen',
                tribe: t1,
                games: 13,
                partners: [['Same', 7, t1], ['Other', 2, t2], ['Unaligned', 4, null]]
            });
            guideSims.pn = mountSvgGraph(pnEl, 'pn', pnData.nodes, pnData.links, guideSims.pn, null, false);
        }
    }

    if ($('#guideMapHm').length > 0) {
        renderGuideGraphs();
        $(window).on('resize', renderGuideGraphs);
    }

    const dates = window.NETWORK_DATES;
    const snapshots = window.NETWORK_SNAPSHOTS;
    if (!dates?.length || !snapshots || $('#networkWrapper').length === 0) return;

    const $wrapper = $('#networkWrapper');
    const $searchInput = $('#playerName');
    const $datePicker = $('#datePicker').attr({ min: dates[0], max: dates[dates.length - 1] });
    const $prevBtn = $('#prevDateBtn');
	const $nextBtn = $('#nextDateBtn');
	const $earliestBtn = $('#earliestDateBtn');
	const $latestBtn = $('#latestDateBtn');
    const $headerTitle = $('#tribeMapTitle');
    const $legend = $('#tribeMapLegend');
    const $ledger = $('#tribeMapLedger');

    let currentIndex = dates.length - 1;
    let simulation = null;
    let isInternalSearch = false;

    const formatShortDate = dateStr => {
        const d = new Date(`${dateStr}T00:00:00`);
        return isNaN(d) ? dateStr : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    function setSearchPlayer(name) {
        isInternalSearch = true;
        $searchInput.val(name).trigger('change');
        isInternalSearch = false;
    }

    function clearSearch() {
        isInternalSearch = true;
        $searchInput.val('');
        $('#root-db-btn').attr('href', '#').addClass('disabled');
        isInternalSearch = false;
    }

    function findPlayer(query) {
        const q = (query || '').trim().toLowerCase();
        if (!q) return null;
        const name = Object.keys(constellations).find(k => k.toLowerCase() === q);
        return name ? { name, data: constellations[name] } : null;
    }

    function findTribe(query) {
        const q = (query || '').trim().toLowerCase();
        if (!q) return null;
        for (const snap of Object.values(snapshots)) {
            const match = Object.keys(snap).find(k => k.toLowerCase() === q);
            if (match) return match;
        }
        return null;
    }

    function setView(view, { tribe = null, player = null, dateIdx = null } = {}) {
		currentView = view;

		if (view === 'hm') {
			activeTribe = null;
			selectedPlayer = null;
			if (dateIdx != null && !isNaN(dateIdx)) currentIndex = dateIdx;
			clearSearch();
		} else if (view === 'hn') {
			activeTribe = tribe;
			selectedPlayer = null;
			if (dateIdx != null && !isNaN(dateIdx)) currentIndex = dateIdx;
			clearSearch();
		} else if (view === 'pn') {
			activeTribe = null;
			if (player) setSearchPlayer(player);
		}
		updateView();
	}

    function syncUrl() {
        const query = currentView === 'pn' ? '?tab=circle'
                    : (currentView === 'hn' && activeTribe) ? `?clearing=${encodeURIComponent(activeTribe.toLowerCase())}`
                    : '';
        const fullPath = `${window.location.pathname}${query}#view`;

        history.replaceState?.(null, null, fullPath);

        $('.season-btn').each(function () {
            const baseHref = ($(this).attr('href') || '').split(/[?#]/)[0];
            if (baseHref) $(this).attr('href', `${baseHref}${query}#view`);
        });
    }

    function getTribeLifespan(tribe) {
        if (!tribe) return null;
        const activeIndices = [], segments = [];
        let currentSeg = null, peakIndex = -1, peakCount = 0;

        dates.forEach((d, idx) => {
            const count = snapshots[d]?.[tribe]?.length || 0;
            if (count > 0) {
                activeIndices.push(idx);
                if (count > peakCount) {
                    peakCount = count;
                    peakIndex = idx;
                }
                if (currentSeg) {
                    currentSeg.endIndex = idx;
                } else {
                    currentSeg = { startIndex: idx, endIndex: idx };
                    segments.push(currentSeg);
                }
            } else {
                currentSeg = null;
            }
        });

        if (!activeIndices.length) return null;

        const milestones = [];
        segments.forEach((seg, segIdx) => {
            milestones.push({
                idx: seg.startIndex,
                label: `${segIdx === 0 ? 'Settled' : 'Revived'} ${formatShortDate(dates[seg.startIndex])}`
            });

            if (peakIndex > seg.startIndex && peakIndex < seg.endIndex) {
                milestones.push({
                    idx: peakIndex,
                    label: `Culminated ${formatShortDate(dates[peakIndex])}`
                });
            }

            if (seg.endIndex < dates.length - 1) {
                const dissolvedDate = dates[seg.endIndex + 1] || dates[seg.endIndex];
                milestones.push({
                    idx: seg.endIndex,
                    label: `Dissolved ${formatShortDate(dissolvedDate)}`
                });
            } else {
                milestones.push({
                    idx: seg.endIndex,
                    label: `Persisted ${formatShortDate(dates[seg.endIndex])}`
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

    function getSeasonChronicle(refIndex = currentIndex) {
        const allTribes = new Set();
        dates.forEach(d => {
            Object.keys(snapshots[d] || {}).forEach(t => {
                if (snapshots[d][t]?.length > 0) allTribes.add(t);
            });
        });

        const events = [];
        allTribes.forEach(tribe => {
            const life = getTribeLifespan(tribe);
            if (!life?.milestones.length) return;

            if (refIndex < life.firstIndex) return;

            const validMilestones = life.milestones.filter(m => {
                if (m.label.startsWith('Culminated') || m.label.startsWith('Persisted')) return false;
                return m.label.startsWith('Dissolved') ? refIndex > m.idx : m.idx <= refIndex;
            });
            if (!validMilestones.length) return;

            const latest = validMilestones[validMilestones.length - 1];
            const isAlive = (snapshots[dates[refIndex]]?.[tribe]?.length > 0);

            events.push({
                tribe,
                foundingIdx: life.firstIndex,
                idx: latest.idx,
                label: latest.label,
                isDissolved: !isAlive,
                icon: config.tribes?.[tribe]?.icon || ''
            });
        });

        return events.sort((a, b) => a.foundingIdx - b.foundingIdx || a.tribe.localeCompare(b.tribe));
    }

    function getPlayerHistory(playerName) {
        const segments = [];
        let active = null;

        dates.forEach((dateStr, idx) => {
            const snap = snapshots[dateStr] || {};
            const tribe = normalizeTribe(Object.keys(snap).find(t => snap[t]?.some(m => m[0] === playerName)));

            if (tribe) {
                const prev = segments[segments.length - 1];
                if (active?.tribe === tribe) {
                    active.endDate = dateStr;
                    active.endIndex = idx;
                } else if (!active && prev?.tribe === tribe && idx - prev.endIndex <= 3) {
                    active = segments.pop();
                    active.endDate = dateStr;
                    active.endIndex = idx;
                } else {
                    if (active) segments.push(active);
                    active = { tribe, startDate: dateStr, startIndex: idx, endDate: dateStr, endIndex: idx };
                }
            } else if (active) {
                segments.push(active);
                active = null;
            }
        });
        if (active) segments.push(active);

        const currentTribe = getPlayerTribe(playerName);
        return segments.reverse().map((seg, i) => ({
            ...seg,
            isCurrent: i === 0 && seg.endIndex === dates.length - 1 && seg.tribe === currentTribe
        }));
    }

    const badgeButtonHtml = ({ tribe, dateIndex, label, isCurrent, icon }) => `
		<button type="button" class="allegiance-badge ${isCurrent ? 'is-current' : 'is-past'}"
				data-tribe="${tribe}" data-date-index="${dateIndex}">
			${icon ? `<img src="${icon}" alt="${tribe}" class="allegiance-icon">` : ''}
			<span class="allegiance-date">${label}</span>
		</button>`;

    const renderLegend = (title, items) => {
        const listHtml = items.map(([color, text]) =>
            `<div class="legend-item"><span class="legend-dot" style="background: ${color}"></span><span>${text}</span></div>`
        ).join('');
        $legend.html(`<div class="hud-title">${title}</div>${listHtml}`);
    };

    function renderChronicleToolbar() {
        let $chronicle = $('#chronicleToolbar');
        if (!$chronicle.length) {
            $chronicle = $('<div id="chronicleToolbar" class="chronicle-toolbar"></div>').insertAfter('#tribeMapContainer');
        }
        if (currentView === 'pn') {
            $chronicle.empty();
            return;
        }

        const events = getSeasonChronicle(currentIndex);
        if (!events.length) {
            $chronicle.empty();
            return;
        }

        const html = events.map(ev => `
            <button type="button"
                    class="chronicle-icon-btn ${ev.isDissolved ? 'is-dissolved' : 'is-active'} ${currentView === 'hn' && activeTribe === ev.tribe ? 'is-selected' : ''}"
                    data-tribe="${ev.tribe}"
                    data-date-index="${ev.idx}">
                <img src="${ev.icon}" alt="${ev.tribe}">
                <span class="tooltip-text">${ev.label}</span>
            </button>`).join('');

        $chronicle.html(html);
    }

    function updateChrome(snapshot) {
        $wrapper.attr('data-view', currentView);
        renderChronicleToolbar();

        if (currentView === 'pn' && selectedPlayer) {
            renderLegend('Companions', [
                [same_tribe, 'Same homeland'],
                [other_tribe, 'Other homeland'],
                [unaligned, 'Unaligned']
            ]);

            const rawTribe = getPlayerTribe(selectedPlayer);
            const currentTribe = rawTribe
                ? (Object.keys(snapshot || {}).find(k => k.toLowerCase() === rawTribe.toLowerCase()) || rawTribe)
                : null;

            if (currentTribe) {
                const members = [...(snapshot?.[currentTribe] || [])].sort((a, b) => b[2] - a[2]);
                const isHerald = members.length > 0 && members[0][0] === selectedPlayer;
                const member = members.find(m => m[0] === selectedPlayer);
                const fidelity = member ? Number(member[1]) : 0;
                const rank = fidelity > 80 ? 'Partisan' : (fidelity >= 50 ? 'Squire' : 'Friend');

                $headerTitle.html(`
                    <div class="hud-title">${currentTribe} ${rank}</div>
                    ${isHerald ? `<button type="button" class="hud-herald-btn" data-player="${selectedPlayer}" data-tribe="${currentTribe}">Homeland Herald</button>` : ''}
                `);
            } else {
                $headerTitle.html('<div class="hud-title">Lone Wanderer</div>');
            }

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
                        icon: config.tribes?.[s.tribe]?.icon
                    });
                }).join('');
            $ledger.html(`<div class="hud-title">Allegiances</div>${badges}`);
            return;
        }

        if (currentView === 'hn' && activeTribe) {
            renderLegend('Fidelity', [
                [same_tribe, 'Partisan'],
                [`color-mix(in srgb, ${same_tribe} 50%, ${other_tribe})`, 'Squire'],
                [other_tribe, 'Friend']
            ]);

            const members = [...(snapshot?.[activeTribe] || [])].sort((a, b) => b[2] - a[2]);
            const heraldName = members[0]?.[0] || null;

            $headerTitle.html(`
                <div class="hud-title">${activeTribe} Homeland</div>
                ${heraldName ? `<button type="button" class="hud-herald-btn" data-player="${heraldName}" data-tribe="${activeTribe}">${heraldName}</button>` : ''}
            `);

            const life = getTribeLifespan(activeTribe);
            const badges = life ? life.milestones.map(m => badgeButtonHtml({
                tribe: activeTribe,
                dateIndex: m.idx,
                label: m.label,
                isCurrent: currentIndex === m.idx
            })).join('') : '';
            $ledger.html(badges ? `<div class="hud-title">Chronicle</div>${badges}` : '');
        }
    }

    function renderGraph(snapshot) {
        updateChrome(snapshot);
        const { nodes, links } = buildGraphData(snapshot);
        simulation = mountSvgGraph(document.getElementById('tribeMapSvg'), currentView, nodes, links, simulation, activeTribe, true);
    }

    function updateView() {
        const activeTab = currentView === 'pn' ? 'circle' : 'map';
        $('.homelands-tab-link[data-tab]').removeClass('active')
            .filter(`[data-tab="${activeTab}"]`).addClass('active');

        $('.season-selector-group, .footer-table').show();

        if (currentView === 'pn') {
            selectedPlayer = findPlayer($searchInput.val())?.name || null;
            $wrapper.toggle(Boolean(selectedPlayer));
            if (selectedPlayer) {
                renderGraph(snapshots[dates[dates.length - 1]]);
            } else {
                simulation?.stop();
            }
            syncUrl();
            return;
        }

        $wrapper.show();
        let minIdx = 0, maxIdx = dates.length - 1;

        if (currentView === 'hn' && activeTribe) {
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
                }
            }
        }

        currentIndex = Math.max(minIdx, Math.min(maxIdx, currentIndex));

        const selectedDate = dates[currentIndex];
        $datePicker.attr({ min: dates[minIdx], max: dates[maxIdx] }).val(selectedDate);
        $prevBtn.add($earliestBtn).prop('disabled', currentIndex <= minIdx);
        $nextBtn.add($latestBtn).prop('disabled', currentIndex >= maxIdx);

        if (snapshots[selectedDate]) renderGraph(snapshots[selectedDate]);
        syncUrl();
    }

    function stepDate(dir) {
        const life = currentView === 'hn' ? getTribeLifespan(activeTribe) : null;
        if (life) {
            const nextIdx = life.activeIndices[life.activeIndices.indexOf(currentIndex) + dir];
            if (nextIdx !== undefined) {
                currentIndex = nextIdx;
                updateView();
            }
            return;
        }
        currentIndex += dir;
        updateView();
    }

    $(document).on('click', '.chronicle-icon-btn', function (e) {
        e.stopPropagation();
        const tribe = $(this).data('tribe');
        const isDissolved = $(this).hasClass('is-dissolved');
        const dateIdx = parseInt($(this).data('date-index'), 10);
        if (!tribe) return;

        if (currentView === 'hn' && activeTribe === tribe) {
            setView('hm');
        } else {
            setView('hn', {
                tribe,
                dateIdx: isDissolved && !isNaN(dateIdx) ? dateIdx : null
            });
        }
    });

    $ledger.on('click', '.allegiance-badge', function (e) {
        e.stopPropagation();
        const tribe = $(this).data('tribe');
        const dateIdx = parseInt($(this).data('date-index'), 10);
        if (tribe && !isNaN(dateIdx)) setView('hn', { tribe, dateIdx });
    });

    $headerTitle.on('click', '.hud-herald-btn', function (e) {
        e.stopPropagation();
        const player = $(this).data('player');
        const tribe = $(this).data('tribe') || activeTribe;
        if (player && typeof window.openTierModal === 'function') {
            window.openTierModal('frog', player, tribe);
        }
    });

    $searchInput.on('input change', function () {
        if (isInternalSearch) return;
        const val = $(this).val().trim();
        setView(val ? 'pn' : 'hm');
    });

    $(document).on('click', '.homelands-tab-link[data-tab]', function (e) {
        if ($('#networkWrapper').length === 0) return;
        const tab = $(this).data('tab');
        if (tab === 'leaderboard') return;
        e.preventDefault();

        if (tab === 'circle') {
            const player = selectedPlayer || $searchInput.val().trim() || localStorage.getItem('selectedPlayer') || '';
            setView('pn', { player });
        } else {
            setView('hm');
        }
    });

    $prevBtn.on('click', () => stepDate(-1));
    $nextBtn.on('click', () => stepDate(1));
    $earliestBtn.on('click', () => {
        const life = currentView === 'hn' ? getTribeLifespan(activeTribe) : null;
        currentIndex = life ? life.firstIndex : 0;
        updateView();
    });

    $latestBtn.on('click', () => {
        const life = currentView === 'hn' ? getTribeLifespan(activeTribe) : null;
        currentIndex = life ? life.lastIndex : dates.length - 1;
        updateView();
    });

    $datePicker.on('change', function () {
        const idx = dates.findIndex(d => d >= $(this).val());
        currentIndex = idx !== -1 ? idx : dates.length - 1;
        updateView();
    });

    $(window).on('resize', updateView);

    const urlParams = new URLSearchParams(window.location.search);
    const clearingParam = urlParams.get('clearing') || urlParams.get('tribe');
    const playerParam = urlParams.get('player');
    const tabParam = urlParams.get('tab');
    const hash = window.location.hash.replace('#', '');

    if (clearingParam) {
        const matched = findTribe(clearingParam);
        setView(matched ? 'hn' : 'hm', { tribe: matched });
    } else if (tabParam === 'circle' || hash === 'circle' || playerParam) {
        const initialPlayer = (playerParam || $searchInput.val() || localStorage.getItem('selectedPlayer') || '').trim();
        setView('pn', { player: initialPlayer });
    } else {
        setView('hm');
    }

    setTimeout(() => { if (currentView !== 'pn') clearSearch(); }, 60);
});

/* =========================================================================
   --- 11. SECRETS ENGINE ---
   ========================================================================= */

document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;

    function checkFinalCompletion() {
        const required = ['watcher-found', 'nut-found', 'berry-found', 'ciphers-found', 'warden-found'];
        const allFound = required.every(key => localStorage.getItem(key) === 'true');

        if (allFound) {
            body.classList.add('secrets-ended');
            localStorage.setItem('secrets-ended', 'true');
        }
    }
	
	function triggerMysticTransition(callback) {
		const gate = document.getElementById('mystic-gate');
		$(gate).fadeIn(600, function() {
			if (callback) callback();
			$(gate).fadeOut(1000);
		});
	}

    const isEnded = localStorage.getItem('secrets-ended') === 'true';
    const isWatcherFound = localStorage.getItem('watcher-found') === 'true';
    const isNutFound = localStorage.getItem('nut-found') === 'true';
    const isBerryFound = localStorage.getItem('berry-found') === 'true';
    const isCiphersFound = localStorage.getItem('ciphers-found') === 'true';
	const isWardenFound = localStorage.getItem('warden-found') === 'true';
    const isHofUnlocked = localStorage.getItem('hof-unlocked') === 'true';

    if (isWatcherFound) body.classList.add('watcher-found');
    if (isNutFound) body.classList.add('nut-found');
    if (isBerryFound) body.classList.add('berry-found');
    if (isCiphersFound) {
        body.classList.add('ciphers-found');
        updateMysticUI();
    }
	if (isWardenFound) body.classList.add('warden-found');
    if (isEnded) body.classList.add('secrets-ended');
    if (isHofUnlocked) body.classList.add('hof-unlocked');

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
	
    const watcherBtn = document.getElementById('watcher-secret');
    if (watcherBtn) {
        watcherBtn.addEventListener('click', () => {
            body.classList.add('watcher-found');
            localStorage.setItem('watcher-found', 'true');
            checkFinalCompletion();
            window.dispatchEvent(new Event('scroll'));
        });
    }

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

if (btnEngrave && inputZone) {
    btnEngrave.addEventListener('click', () => {
        btnEngrave.style.display = 'none';
        inputZone.style.display = 'block';
    });
}

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
