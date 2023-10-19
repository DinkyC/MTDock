let currentIndex = 1;

function fetchTranslation(index, dir) {
    fetch(`${CONFIG.API_ENDPOINT}/get-translation?table=final_translation&direction=${dir}&id=${currentIndex}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('title').innerText = data.title;
            document.getElementById('text').innerText = data.text;
            
            currentIndex = data.id;  // Assuming the API returns the id of the fetched translation

            // Update the hidden input's value
            document.getElementById('currentIndexInput').value = currentIndex;

        })
        .catch(error => {
            console.error('Error fetching translation:', error);
        });
}


window.onload = function() {
    // Event listeners for the buttons
    document.querySelectorAll('.custom-button').forEach(function(button) {
        if (button.textContent.includes("Next Translation")) {
            button.addEventListener('click', function() {
                fetchTranslation(currentIndex, 'next');
            });
        } else if (button.textContent.includes("Previous Translation")) {
            button.addEventListener('click', function() {
                fetchTranslation(currentIndex, 'prev');
            });
        }
    });

    // Initial fetch when the window loads
    fetchTranslation(currentIndex, 'next');
};

