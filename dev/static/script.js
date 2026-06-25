/* =========================================================================
   --- 9. GLOBAL FILTER SYNC & TOOLTIPS ---
   ========================================================================= */

// 1. Initialisation dynamique du tooltip & Gestion de l'affichage Mobile
$(document).on('mouseenter touchstart', '.player-click-target', function(e) {
    // Texte mis à jour pour refléter la redirection vers les graphiques
    if (!this.hasAttribute('data-tooltip')) {
        $(this).attr('data-tooltip', 'Double-click to view player trends');
    }
    
    if (e.type === 'touchstart') {
        $('.player-click-target').not(this).removeClass('expanded');
        $(this).addClass('expanded');
    }
});

// Ferme le tooltip mobile au clic extérieur
$(document).on('touchstart', function(e) {
    if (!$(e.target).closest('.player-click-target').length) {
        $('.player-click-target').removeClass('expanded');
    }
});

// 2. Handle double-click to save player and redirect to Trends
$(document).on('dblclick', '.player-click-target', function() {
    // Récupère le texte sélectionné ou le texte brut de la cellule en secours
    const selectedText = window.getSelection().toString().trim() || $(this).text().trim();
    
    if (selectedText && selectedText.length > 1 && selectedText.length < 30 && !selectedText.includes('\n')) {
        // 1. On stocke le joueur pour que la page Trends le récupère au chargement
        localStorage.setItem('selectedPlayer', selectedText);
        
        // 2. On redirige instantanément vers la page Trends
        window.location.href = 'trends.html'; 
    }
});

// 3. Global Input Sync & Cleanup (Utile si on vide le champ directement sur la page Trends)
$(document).on('input search', '.dataTables_filter input, #playerName', function() {
    const value = $(this).val().trim();
    
    if (value) {
        localStorage.setItem('selectedPlayer', value);
    } else {
        localStorage.removeItem('selectedPlayer');
    }
});
