function fetchTranslation(index) {
    const url = `https://ousoxg55w5-vpce-0ebe9f0a90313d9ea.execute-api.us-west-1.amazonaws.com/prod/get-translation?table=final_translation&id=${index}`;
    
    import('node-fetch').then(fetch => {
        fetch.default(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Title:", data.title);
                console.log("Text:", data.text);
            })
            .catch(error => {
                console.error('Error fetching translation:', error);
            });
    });
}

fetchTranslation(100);

