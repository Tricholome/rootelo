// --- 1. LEADERBOARD ---
if ($('#leaderboard').length > 0) {
    
    // 1. VARIABLE D'ÉTAT : Définit si on veut voir les unranked ou non
    // On met 'false' par défaut pour filtrer d'emblée
    let showUnranked = false; 

    $.extend($.fn.dataTable.ext.type.order, { 
        "rank-pre": function (d) { return d === "-" ? 9999 : parseInt(d); } 
    });

    const table = $('#leaderboard').DataTable({
        "order": [[3, "desc"]],
        "responsive": true, 
        "pageLength": 50,
        "dom": '<"top"lf>rt<"bottom"ip><"clear">',
        "columnDefs": [ 
            { "targets": 0, "type": "rank" },
            { "targets": 2, "className": "player-name-cell" },
            { "className": "elo-cell" },
            { "className": "numeric-cell", "targets": [0, 3, 4, 5, 6, 7, 8] }
        ],
        "language": { "searchPlaceholder": "Player name" },
        "initComplete": function(settings, json) {
            // On injecte la case
            $('.dataTables_length').append(`
                <label class="dt-checkbox-label">
                    <input type="checkbox" id="tierFilterCheckbox"> Show unranked players
                </label>
            `);
        }
    });

    // 2. FILTRAGE : Utilise la variable d'état au lieu du DOM
    $.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
        if (settings.nTable.id !== 'leaderboard') return true;
        
        // Si la variable est true, on montre tout
        if (showUnranked) return true; 
        
        // Sinon, on masque si la première colonne est "-"
        return data[0].trim() !== "-";
    });

    // 3. Mise à jour de l'état au clic (Délégation d'événement)
    $(document).on('change', '#tierFilterCheckbox', function() {
        showUnranked = $(this).is(':checked'); // Met à jour la variable
        table.draw(); // Redessine
    });
}
