var dataTable; // Declare dataTable outside the document.ready function
var databaseTable; // Declare table for database
var currentPage = 1; // Initialize the current page
$(document).ready(function() {
    // Initialize DataTable
    dataTable = $('#data-table').DataTable({
        "ajax": {
            "url": "/get_status",
            "dataSrc": ""
        },
        "columns": [
            { "data": "status" },
            { "data": "title" },
            { "data": "lang_to" },
            { "data": "lang_from" },
            {
                "data": "id",
                "render": function(data, type, row) {
                    // Added a new data-newid attribute for the button
                    return '<a href="#" class="btn btn-primary remove-button" data-id="' + data + '" data-lang_to="' + row.lang_to + '" data-lang_from="' + row.lang_from + '">Remove</a>';
                }
            }
        ]
    });

    // Handle Remove button click event
    $('#data-table').on('click', '.remove-button', function(e) {
        e.preventDefault();
        var lang_to = $(this).data('lang_to');
        var lang_from = $(this).data('lang_from');
        var id = $(this).data('id');  // Retrieve the new id from the button's data attribute
        removeItem(id, lang_from, lang_to);  // Pass both IDs to the deleteTrans function
    });

    // Function to remove item via AJAX
    function removeItem(id, lang_from, lang_to) {
        $.ajax({
            url: '/remove_from_queue/' + id,
            type: 'DELETE',
            contentType: 'application/json',  // Set content type to JSON
            data: JSON.stringify({  // Stringify the data
                "lang_from": lang_from,
                "lang_to": lang_to
            }),
            success: function(response) {
                if (response.success) {
                    // Removal was successful
                    dataTable.clear().draw();
                    dataTable.ajax.reload();
                } else {
                    // Display an error message, if needed
                    console.error('Error removing item: ' + response.error);
                }
            },
            error: function() {
                // Handle other errors, if needed
                console.error('Error removing item');
            }
        });
    }
});

$(document).ready(function() {

    function fetchData(page) {
        $.ajax({
            url: "/get_articles",
            data: {
                page: page,
                per_page: 2
            },
            success: function(data) {
                databaseTable.clear().rows.add(data).draw();
                updateButtonStates();
            },
            error: function(xhr, textStatus, errorThrown) {
                console.log("AJAX Error:", errorThrown);
            }
        });
    }

var databaseTable = new DataTable(document.querySelector('#database-table'), {
    searching: false,
    lengthChange: false,
    paging: false,
    columns: [
        { data: "title", width: "85px" },
        { data: "text" },
        {
            data: "id",
            width: "70px",
            render: function(data, type, row) {
                return '<a href="#" class="btn btn-primary queue-button" data-id="' + data + '">Queue</a>';
            }
        },
        {
            data: null,
            width: "100px",
            render: function(data, type, row) {
                return `
                    <select data-row-id="${row.id}" class="from-lang">
                        <option value="en">English</option>
                        <option value="es">Spanish</option>
                        <option value="ja">Japanese</option>
                        <option value="pt">Portuguese</option>
                    </select>
                    To:
                    <select data-row-id="${row.id}" class="to-lang">
                        <option value="en">English</option>
                        <option value="es">Spanish</option>
                        <option value="ja">Japanese</option>
                        <option value="pt">Portuguese</option>
                    </select>
                `;
            }
        }
    ]
});



document.addEventListener("DOMContentLoaded", function() {
    const table = document.querySelector('#database-table');

    table.addEventListener('change', function(event) {
        const target = event.target;

        // Check if the event target has the class 'from-lang' or 'to-lang'
        if (target.classList.contains('from-lang') || target.classList.contains('to-lang')) {
            const rowId = target.dataset.rowId;
            const inputId = target.classList.contains('from-lang') ? `selectedFromLang-${rowId}` : `selectedToLang-${rowId}`;
            const correspondingInput = document.getElementById(inputId);

            if (correspondingInput) {
                correspondingInput.value = target.value;
            }
            
            console.log(`Selected ${target.classList.contains('from-lang') ? 'From' : 'To'} Language:`, target.value);
        }
    });
});




    // Fetch initial data
    fetchData(currentPage);

    // Go to the previous page
    $('#previous-button').click(function() {
        if (currentPage > 1) {
            currentPage--;
            fetchData(currentPage);
        }
    });

    // Go to the next page
    $('#next-button').click(function() {
        currentPage++;
        fetchData(currentPage);
    });

    // Update button states based on the current page
    function updateButtonStates() {
        // Assuming you know the total number of pages. If not, this logic needs adjustment.
        $('#previous-button').prop('disabled', currentPage === 1);
        $('#next-button').prop('disabled', currentPage === 3200); // replace 3000 with your total pages count
    }

    // Handle Remove button click event
    $('#database-table').on('click', '.queue-button', function(e) {
        e.preventDefault();
        var id = $(this).data('id');
        queueItem(id);
    });

    function queueItem(id) {
        var from_lang = document.getElementById('from_lang');
        var to_lang = document.getElementById('to_lang');
        var url = '/queue/' + id + '?from_lang=' + from_lang.value + '&to_lang=' + to_lang.value;

        $.ajax({
            url: url,
            type: 'POST',
            success: function(response) {
                if (response.success) {
                    fetchData(currentPage);
                    dataTable.ajax.reload();
                } else {
                    console.error('Error queuing item: ' + response.error);
                }
            },
            error: function() {
                console.error('Error removing item');
            }
        });
    }

    function fetchTitle(title) {
        $.ajax({
            url: "/get_articles",
            data: {
                title: title
            },
            success: function(data) {
                databaseTable.clear().rows.add(data).draw();
                updateButtonStates();
            },
            error: function(xhr, textStatus, errorThrown) {
                console.log("AJAX Error:", errorThrown);
            }
        });
    }

    $('#searchButton').click(function(e) {
        e.preventDefault();
        var title = $('#articleSearch').val();
        fetchTitle(title);
    });

});

