var dataTable; // Declare dataTable outside the document.ready function

$(document).ready(function() {
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
                    return '<a href="#" class="btn btn-primary remove-button" data-id="' + data + '">Remove</a>';
                }
            }
        ]
    });

    // Handle Remove button click event
    $('#data-table').on('click', '.remove-button', function(e) {
        e.preventDefault();
        var id = $(this).data('id');
        removeItem(id);
    });

    // Function to remove item via AJAX
    function removeItem(id) {
        $.ajax({
            url: '/remove_from_queue/' + id,
            type: 'DELETE',
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

