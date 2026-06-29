// --- 1. LEADERBOARD ---
    if ($('#leaderboard').length > 0) {
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

        // FILTRAGE DÉFENSIF
        $.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
            if (settings.nTable.id !== 'leaderboard') return true;

            const $checkbox = $('#tierFilterCheckbox');
            
            // Si la case existe et est cochée -> On montre tout
            if ($checkbox.length && $checkbox.is(':checked')) {
                return true;
            }

            // Sinon (case non trouvée OU non cochée) -> On filtre les "-"
            return data[0].trim() !== "-";
        });

        // Event listener pour rafraîchir au changement
        $(document).on('change', '#tierFilterCheckbox', function() {
            table.draw();
        });
    }
