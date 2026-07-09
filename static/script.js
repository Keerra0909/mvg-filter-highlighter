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

    function extractDateNumber(filename) {
        // Try to match YYYY-MM-DD format (usually Excel) and extract the Day (DD)
        const dateMatch = filename.match(/\d{4}-\d{2}-(\d{2})/);
        if (dateMatch) {
            return dateMatch[1];
        }
        
        // Otherwise, extract the first 1 or 2 digit number (usually PDF like "07 DE JULIO")
        const match = filename.match(/\b([0-3]?\d)\b/);
        if (match) {
            return match[1].padStart(2, '0');
        }
        
        return null;
    }

    function checkFiles() {
        const warningDiv = document.getElementById('date-warning');
        if (excelInput.files.length > 0 && pdfInput.files.length > 0) {
            submitBtn.disabled = false;
            
            // Check if dates match
            const excelDate = extractDateNumber(excelInput.files[0].name);
            const pdfDate = extractDateNumber(pdfInput.files[0].name);
            
            if (excelDate && pdfDate && excelDate !== pdfDate) {
                warningDiv.classList.remove('hidden');
            } else {
                warningDiv.classList.add('hidden');
            }
        } else {
            submitBtn.disabled = true;
            if (warningDiv) warningDiv.classList.add('hidden');
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

    // ── Screen references ──
    const screenPassword = document.getElementById('screen-password');
    const screenLobby    = document.getElementById('screen-lobby');
    const screenApp      = document.getElementById('screen-app');

    const passwordInput  = document.getElementById('password-input');
    const passwordBtn    = document.getElementById('password-btn');
    const passwordError  = document.getElementById('password-error');
    const selectedLobby  = document.getElementById('selected-lobby');

    function showScreen(screen) {
        [screenPassword, screenLobby, screenApp].forEach(s => s.style.display = 'none');
        screen.style.display = 'flex';
    }

    // Check for 10-minute active session on load
    const authTimestamp = localStorage.getItem('mvg_auth_timestamp');
    const TEN_MINUTES = 10 * 60 * 1000;
    if (authTimestamp && (Date.now() - parseInt(authTimestamp) < TEN_MINUTES)) {
        // Session is valid. Extend it and skip password screen.
        localStorage.setItem('mvg_auth_timestamp', Date.now().toString());
        showScreen(screenLobby);
    } else {
        // Expired or no session
        localStorage.removeItem('mvg_auth_timestamp');
    }

    // Step 1 → Step 2: Password check
    passwordBtn.addEventListener('click', () => {
        if (passwordInput.value.trim().toUpperCase() === 'MVG2026') {
            localStorage.setItem('mvg_auth_timestamp', Date.now().toString());
            showScreen(screenLobby);
        } else {
            passwordError.style.display = 'block';
        }
    });
    passwordInput.addEventListener('keydown', e => { if (e.key === 'Enter') passwordBtn.click(); });

    // Step 2 → Step 3: Lobby selection
    document.querySelectorAll('.lobby-card').forEach(card => {
        card.addEventListener('click', () => {
            card.classList.add('selected');
            selectedLobby.value = card.dataset.lobby;
            const name = card.querySelector('.lobby-name').textContent;
            document.getElementById('app-lobby-label').textContent = '📍 ' + name;
            setTimeout(() => showScreen(screenApp), 280);
        });
    });

    // "Cambiar" button to go back to Lobby selection
    document.getElementById('change-lobby-btn').addEventListener('click', () => {
        document.querySelectorAll('.lobby-card').forEach(c => c.classList.remove('selected'));
        showScreen(screenLobby);
    });


    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        statusDiv.classList.remove('hidden');
        resultDiv.classList.add('hidden'); // hide previous results while processing
        const errorBox = document.getElementById('smart-error');
        if (errorBox) errorBox.classList.add('hidden');
        const successStatus = document.getElementById('success-status');
        if (successStatus) successStatus.classList.add('hidden');
        
        const formData = new FormData(form);
        
        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            statusDiv.classList.add('hidden');
            
            if (response.ok) {
                const successStatus = document.getElementById('success-status');
                if (successStatus) successStatus.classList.remove('hidden');
                
                resultDiv.classList.remove('hidden');
                
                // Populate summary stats
                if (data.stats) {
                    if (data.stats.lobby) {
                        document.getElementById('summary-lobby-title').textContent = data.stats.lobby;
                    }

                    if (data.stats.duplicates && data.stats.duplicates.length > 0) {
                        document.getElementById('stat-duplicates').textContent = data.stats.duplicates.join(', ');
                        document.getElementById('label-duplicates').textContent = `${data.stats.duplicates.length} Duplicates`;
                    } else {
                        document.getElementById('stat-duplicates').textContent = 'None';
                        document.getElementById('label-duplicates').textContent = 'Duplicates';
                    }
                    
                    if (data.stats.excel_total > 0 && (data.stats.total_green || 0) === 0) {
                        document.getElementById('anomaly-warning').classList.remove('hidden');
                    } else {
                        document.getElementById('anomaly-warning').classList.add('hidden');
                    }
                    
                    document.getElementById('stat-excel-total').textContent = data.stats.excel_total || 0;
                    document.getElementById('stat-green').textContent = data.stats.total_green || 0;
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
                        document.getElementById('label-checkouts').textContent = `${data.stats.checkouts.length} Checked Out`;
                    } else {
                        document.getElementById('stat-checkouts').textContent = 'None';
                        document.getElementById('label-checkouts').textContent = 'Checked Out';
                    }
                    
                    if (data.stats.missing_rooms && data.stats.missing_rooms.length > 0) {
                        document.getElementById('stat-missing').textContent = data.stats.missing_rooms.join(', ');
                        document.getElementById('label-missing').textContent = `${data.stats.missing_rooms.length} Missing from PDF`;
                    } else {
                        document.getElementById('stat-missing').textContent = 'None';
                        document.getElementById('label-missing').textContent = 'Missing from PDF';
                    }
                    
                    // Calculate Pitchable Rooms
                    const excelTotal = data.stats.excel_total || 0;
                    const numDuplicates = (data.stats.duplicates && data.stats.duplicates.length) ? data.stats.duplicates.length : 0;
                    const numNewMembers = (data.stats.new_members && data.stats.new_members.length) ? data.stats.new_members.length : 0;
                    const numCheckouts = (data.stats.checkouts && data.stats.checkouts.length) ? data.stats.checkouts.length : 0;
                    
                    const pitchableRooms = excelTotal - numDuplicates - numNewMembers - numCheckouts;
                    document.getElementById('stat-pitchable').textContent = pitchableRooms;
                }
                
                downloadBtn.href = data.download_url;
            } else {
                const errorBox = document.getElementById('smart-error');
                const errorText = document.getElementById('smart-error-text');
                if (errorBox && errorText) {
                    errorText.textContent = data.error;
                    errorBox.classList.remove('hidden');
                } else {
                    alert('Error: ' + data.error);
                }
                form.classList.remove('hidden');
            }
        } catch (error) {
            statusDiv.classList.add('hidden');
            form.classList.remove('hidden');
            const errorBox = document.getElementById('smart-error');
            const errorText = document.getElementById('smart-error-text');
            if (errorBox && errorText) {
                errorText.textContent = error.message;
                errorBox.classList.remove('hidden');
            } else {
                alert('An error occurred: ' + error.message);
            }
        }
    });

    const downloadImgBtn = document.getElementById('download-img-btn');
    if (downloadImgBtn) {
        downloadImgBtn.addEventListener('click', () => {
            const summaryGrid = document.querySelector('.summary-grid');
            if (!summaryGrid) return;
            
            // Force vertical mode for capture
            document.body.classList.add('force-vertical-capture');

            // Temporarily set background so it looks good in the image
            const originalBg = summaryGrid.style.backgroundColor;
            summaryGrid.style.backgroundColor = '#1f2937'; // dark background matching app
            summaryGrid.style.padding = '20px';
            summaryGrid.style.borderRadius = '12px';

            // Need to wait slightly for the DOM to update to vertical layout
            setTimeout(() => {
                html2canvas(summaryGrid, {
                    backgroundColor: '#1f2937',
                    scale: 2 // High resolution
                }).then(canvas => {
                    // Restore original styles
                    document.body.classList.remove('force-vertical-capture');
                    summaryGrid.style.backgroundColor = originalBg;
                    summaryGrid.style.padding = '';
                    summaryGrid.style.borderRadius = '';

                    // Trigger download
                    const link = document.createElement('a');
                    link.download = 'Resumen_Cuartos.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                });
            }, 100);
        });
    }

});
