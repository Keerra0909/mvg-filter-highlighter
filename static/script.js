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

    const passwordContainer = document.getElementById('password-container');
    const appContainer = document.getElementById('app-container');
    const passwordInput = document.getElementById('password-input');
    const passwordBtn = document.getElementById('password-btn');
    const passwordError = document.getElementById('password-error');

    passwordBtn.addEventListener('click', () => {
        if (passwordInput.value === 'MVG2026') {
            passwordContainer.style.display = 'none';
            appContainer.style.display = 'block';
        } else {
            passwordError.style.display = 'block';
        }
    });

    passwordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') passwordBtn.click();
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
                
                // Populate summary stats
                if (data.stats) {
                    if (data.stats.duplicates && data.stats.duplicates.length > 0) {
                        document.getElementById('stat-duplicates').textContent = data.stats.duplicates.join(', ');
                        document.getElementById('label-duplicates').textContent = `${data.stats.duplicates.length} Duplicates`;
                    } else {
                        document.getElementById('stat-duplicates').textContent = 'None';
                        document.getElementById('label-duplicates').textContent = 'Duplicates';
                    }
                    
                    document.getElementById('stat-green').textContent = data.stats.total_green || 0;
                    document.getElementById('stat-brackets').textContent = data.stats.total_linked_groups || 0;
                    document.getElementById('stat-presentations').textContent = data.stats.total_presentations || 0;
                    document.getElementById('stat-promos').textContent = data.stats.total_promos || 0;
                    document.getElementById('stat-certs').textContent = data.stats.total_certs || 0;
                    
                    const superShotsCount = data.stats.total_super_shots || 0;
                    const ssBox = document.getElementById('box-supershots');
                    if (superShotsCount > 0) {
                        const mvgRooms = data.stats.super_shots_mvg || [];
                        const greenRooms = data.stats.super_shots_green || [];
                        const allRooms = [...new Set([...mvgRooms, ...greenRooms])].join(', ');
                        
                        document.getElementById('stat-supershots').textContent = superShotsCount;
                        document.getElementById('label-supershots').textContent = '★ Super Shots';
                        document.getElementById('supershots-details').style.display = 'block';
                        document.getElementById('ss-mvg').textContent = mvgRooms.join(', ') || 'None';
                        document.getElementById('ss-green').textContent = greenRooms.join(', ') || 'None';
                        ssBox.style.display = 'block';
                    } else {
                        ssBox.style.display = 'none';
                    }
                    
                    if (data.stats.new_members && data.stats.new_members.length > 0) {
                        document.getElementById('stat-newmembers').textContent = data.stats.new_members.join(', ');
                        document.getElementById('label-newmembers').textContent = `${data.stats.new_members.length} NEW MEMBER (Transfer + M)`;
                    } else {
                        document.getElementById('stat-newmembers').textContent = 'None';
                        document.getElementById('label-newmembers').textContent = 'NEW MEMBER (Transfer + M)';
                    }
                    
                    if (data.stats.checkouts && data.stats.checkouts.length > 0) {
                        document.getElementById('stat-checkouts').textContent = data.stats.checkouts.join(', ');
                        document.getElementById('label-checkouts').textContent = `${data.stats.checkouts.length} Check Outs`;
                    } else {
                        document.getElementById('stat-checkouts').textContent = 'None';
                        document.getElementById('label-checkouts').textContent = 'Check Outs';
                    }
                }
                
                downloadBtn.href = data.download_url;
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
