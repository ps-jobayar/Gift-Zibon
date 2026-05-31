let currentJWT = "", currentPage = 1, isLoading = false, hasMoreItems = true, currentCategory = "All";
let selectedGift = {};

document.getElementById('loadBtn').addEventListener('click', async () => {
    const jwt = document.getElementById('jwtInput').value.trim();
    const errorMsg = document.getElementById('errorMsg');
    const btn = document.getElementById('loadBtn');

    if (!jwt) { 
        errorMsg.textContent = "⚠️ PARSING ERROR: AUTH TOKEN BUFFER CANNOT BE EMPTY."; 
        errorMsg.style.display = "block"; 
        return; 
    }

    currentJWT = jwt; currentPage = 1; hasMoreItems = true; currentCategory = "All";
    document.getElementById('itemsGrid').innerHTML = '';
    errorMsg.style.display = "none"; 
    btn.innerHTML = `<span class="btn-text">⚡ EXTRACTING CLOUD DATA...</span>`; 
    btn.disabled = true;

    await fetchAndRenderItems(true);
    btn.innerHTML = `<span class="btn-text">INITIALIZE SECURE SYSTEM</span>`; 
    btn.disabled = false;
});

async function fetchAndRenderItems(refreshCats = false) {
    if (isLoading || !hasMoreItems) return;
    isLoading = true;

    try {
        const response = await fetch('/api/get_store', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jwt: currentJWT, page: currentPage, limit: 24, category: currentCategory })
        });
        const data = await response.json();

        if (data.success) {
            document.getElementById('loginBox').style.display = 'none';
            document.getElementById('storeBox').style.display = 'block';
            document.getElementById('giftsSent').textContent = `🎁 DISPATCHED TODAY: ${data.sent_today}`;
            
            if (data.wallet) {
                document.getElementById('valDiamond').textContent = `${data.wallet.diamond}`;
                document.getElementById('valGold').textContent = `${data.wallet.gold}`;
                document.getElementById('valTopup').textContent = data.wallet.last_topup;
            }

            if (refreshCats) renderCategoryButtons(data.categories);

            const grid = document.getElementById('itemsGrid');
            data.items.forEach(item => {
                let purePrice = item.price_str.match(/\d+/)[0];
                let cType = item.price_str.includes('💎') ? 'diamond' : 'gold';

                const card = `
                    <div class="vip-card">
                        <div class="card-tag">${item.category}</div>
                        <div class="img-canvas"><img src="/api/image/${item.item_id}" class="card-thumb" onerror="this.src='https://placehold.co/120x120/10121f/ffffff?text=Item'"></div>
                        <div class="pricing-hud">${item.price_str}</div>
                        <div class="time-hud">VALIDITY:<br>${item.expire_date}</div>
                        <button class="card-inject-btn" onclick="openGiftModal('${item.commodity_id}', '${purePrice}', '${cType}')">INITIATE SEND</button>
                    </div>
                `;
                grid.insertAdjacentHTML('beforeend', card);
            });
            hasMoreItems = data.has_more; currentPage++;
        } else { 
            alert("🔒 BYPASS REFUSED: " + data.message); 
        }
    } catch (err) { 
        alert("🛰️ CRITICAL NETWORK FAILURE: CANNOT CONNECT TO CORE TERMINAL."); 
    }
    isLoading = false;
}

function renderCategoryButtons(categories) {
    const bar = document.getElementById('categoryBar');
    bar.innerHTML = '<button class="matrix-cat-btn active" data-cat="All">🎯 ALL MATRIX</button>';
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'matrix-cat-btn'; 
        btn.textContent = cat.toUpperCase();
        btn.onclick = () => {
            document.querySelectorAll('.matrix-cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = cat; currentPage = 1; hasMoreItems = true;
            document.getElementById('itemsGrid').innerHTML = ''; 
            fetchAndRenderItems();
        };
        bar.appendChild(btn);
    });
}

function openGiftModal(id, price, type) {
    selectedGift = { id, price, type };
    document.getElementById('giftModal').style.display = 'flex';
}
function closeModal() { 
    document.getElementById('giftModal').style.display = 'none'; 
}

document.getElementById('confirmSend').addEventListener('click', async () => {
    const rUid = document.getElementById('targetUid').value.trim();
    const msg = document.getElementById('giftMsg').value;
    const btn = document.getElementById('confirmSend');

    if (!rUid) return alert("❌ PROTOCOL REJECTED: RECEIVER UID IS REQUIRED!");
    btn.disabled = true; 
    btn.textContent = "INJECTING PAYLOAD...";

    try {
        const res = await fetch('/api/send_gift', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jwt: currentJWT, receiver_uid: rUid, commodity_id: selectedGift.id, price: selectedGift.price, currency: selectedGift.type, message: msg })
        });
        const data = await res.json();
        alert(data.message);
        if (data.success) {
            closeModal();
            currentPage = 1; hasMoreItems = true; 
            document.getElementById('itemsGrid').innerHTML = '';
            fetchAndRenderItems();
        }
    } catch (e) { 
        alert("⚠️ CRITICAL: TRANSMISSION INJECTION ABORTED."); 
    }
    btn.disabled = false; 
    btn.textContent = "LAUNCH EXPLOIT";
});

window.onscroll = () => { 
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 600) fetchAndRenderItems(); 
};
