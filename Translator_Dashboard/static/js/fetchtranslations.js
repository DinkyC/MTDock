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
    // Retrieve buttons by their IDs
    const nextButton = document.getElementById('next-button');
    const prevButton = document.getElementById('prev-button');

    // Event listeners for the buttons
    if (nextButton) {
        nextButton.addEventListener('click', function() {
            fetchTranslation(currentIndex, 'next');
        });
    }
    
    if (prevButton) {
        prevButton.addEventListener('click', function() {
            fetchTranslation(currentIndex, 'prev');
        });
    }

    fetchTranslation(currentIndex, 'next');
};

