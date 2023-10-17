
let currentIndex = 100; // To keep track of the current translation being shown

function fetchTranslation(index) {
    fetch(`${CONFIG.API_ENDPOINT}/get-translation?table=final_translation&id=${index}`) // Including query parameter for index
        .then(response => response.json())
        .then(data => {
            const titleElement = document.getElementById('title');
            const textElement = document.getElementById('text');

            titleElement.innerText = data.title;
            textElement.innerText = data.text;
        })
        .catch(error => {
            console.error('Error fetching translation:', error);
        });
}

// Function to handle the 'Next' button click
function fetchNextTranslation() {
    currentIndex += 1; // Incrementing the index to fetch the next translation
    fetchTranslation(currentIndex);
}

// Initial fetch when the page loads
window.onload = function() {
    fetchTranslation(currentIndex);
}

