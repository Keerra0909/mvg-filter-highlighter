document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    const excelInput = document.getElementById('excel_file');
    const pdfInput = document.getElementById('pdf_file');
    const excelName = document.getElementById('excel-name');
    const pdfName = document.getElementById('pdf-name');
    const excelArea = document.getElementById('excel-area');
    const pdfArea = document.getElementById('pdf-area');
    const submitBtn = document.getElementById('submit-btn');
    
    const statusDiv = document.getElementById('status');
    const resultDiv = document.getElementById('result');
    const downloadBtn = document.getElementById('download-btn');
    const resetBtn = document.getElementById('reset-btn');

    function checkFiles() {
        if (excelInput.files.length > 0 && pdfInput.files.length > 0) {
            submitBtn.disabled = false;
        } else {
            submitBtn.disabled = true;
        }
    }

    excelInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            excelName.textContent = e.target.files[0].name;
            excelArea.classList.add('has-file');
        } else {
            excelName.textContent = 'Tap to select your list';
            excelArea.classList.remove('has-file');
        }
        checkFiles();
    });

    pdfInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            pdfName.textContent = e.target.files[0].name;
            pdfArea.classList.add('has-file');
        } else {
            pdfName.textContent = 'Tap to select the report';
            pdfArea.classList.remove('has-file');
        }
        checkFiles();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        form.classList.add('hidden');
        statusDiv.classList.remove('hidden');
        
        const formData = new FormData(form);
        
        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            statusDiv.classList.add('hidden');
            
            if (response.ok) {
                resultDiv.classList.remove('hidden');
                document.getElementById('result-text').textContent = data.message;
                downloadBtn.href = data.download_url;
                
                // Auto trigger download after a short delay
                setTimeout(() => {
                    window.location.href = data.download_url;
                }, 1000);
            } else {
                alert('Error: ' + data.error);
                form.classList.remove('hidden');
            }
        } catch (error) {
            statusDiv.classList.add('hidden');
            form.classList.remove('hidden');
            alert('An error occurred: ' + error.message);
        }
    });

    resetBtn.addEventListener('click', () => {
        form.reset();
        excelName.textContent = 'Tap to select your list';
        pdfName.textContent = 'Tap to select the report';
        excelArea.classList.remove('has-file');
        pdfArea.classList.remove('has-file');
        checkFiles();
        
        resultDiv.classList.add('hidden');
        form.classList.remove('hidden');
    });
});
