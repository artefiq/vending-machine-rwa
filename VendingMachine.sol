// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @dev Interface Manual untuk berinteraksi dengan Token (IDRT / $MESIN).
 * Mendefinisikan kode ini agar kontrak kita tahu cara berinteraksi dengan token lain.
 */
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract VendingMachineNative {
    
    // --- 1. VARIABEL UTAMA ---
    IERC20 public paymentToken; // Token Pembayaran (IDRT)
    IERC20 public assetToken;   // Token Saham ($MESIN)
    
    address public owner;       // Admin/Deployer
    uint256 public coffeePrice; // Harga Kopi
    uint256 public totalRevenue;
    
    // Variabel Modal Pokok
    uint256 public cogsPerCup; 

    // --- 2. KEAMANAN ---
    bool private locked; 

    // --- 3. DIVIDEN ---
    uint256 public constant MAGNITUDE = 2**128;
    uint256 public magnifiedDividendPerShare;
    mapping(address => int256) public magnifiedDividendCorrections;
    mapping(address => uint256) public withdrawnDividends;

    // --- 4. GOVERNANCE ---
    mapping(address => bool) public isWhitelistedVendor;
    
    struct Proposal {
        address proposedVendor;
        string description;
        uint256 voteCount;
        bool executed;
        mapping(address => bool) hasVoted;
        uint256 endTime;
    }
    // Karena struct punya mapping, menyimpan di array dan akses via ID
    Proposal[] private proposals;

    // --- 5. EVENTS ---
    event CoffeeOrdered(address indexed buyer, uint256 timestamp);
    event DividendClaimed(address indexed investor, uint256 amount);
    event ProposalCreated(uint256 id, address vendor, string description);
    event Voted(uint256 id, address voter, uint256 weight);
    event VendorWhitelisted(address vendor);
    event RestockPaid(address vendor, uint256 amount);

    // --- CONSTRUCTOR ---
    constructor(
        address _paymentToken, 
        address _assetToken, 
        uint256 _price,
        uint256 _cogs
    ) {
        paymentToken = IERC20(_paymentToken);
        assetToken = IERC20(_assetToken);
        coffeePrice = _price;
        cogsPerCup = _cogs; // Set modal awal
        owner = msg.sender;
        
        // Tambahkan owner sebagai vendor awal (untuk testing)
        isWhitelistedVendor[msg.sender] = true;
    }

    // --- MODIFIERS MANUAL ---
    
    // Pengganti 'Ownable'
    modifier onlyOwner() {
        require(msg.sender == owner, "Hanya Owner");
        _;
    }

    // Pengganti 'ReentrancyGuard'
    modifier noReentrancy() {
        require(!locked, "Reentrancy terdeteksi!");
        locked = true;
        _;
        locked = false;
    }

    // =========================================================
    // FUNGSI 1: BELI KOPI (TRIGGER IOT)
    // =========================================================
    function buyCoffee() external noReentrancy {
        // Cek saldo manual
        uint256 userBal = paymentToken.balanceOf(msg.sender);
        require(userBal >= coffeePrice, "Saldo kurang");

        // Transfer: Pelanggan -> Kontrak
        // Cek return value 'success' secara manual
        bool success = paymentToken.transferFrom(msg.sender, address(this), coffeePrice);
        require(success, "Transfer gagal");

        // Catat Revenue
        totalRevenue += coffeePrice;

        uint256 profit = 0;
        if (coffeePrice > cogsPerCup) {
            profit = coffeePrice - cogsPerCup;
        } else {
            profit = 0;
        }

        // Hitung Dividen (Update global per-share)
        uint256 supply = assetToken.totalSupply();
        if (supply > 0 && profit > 0) {
            magnifiedDividendPerShare += (profit * MAGNITUDE) / supply;
        }

        // EMIT EVENT (Untuk Python/IoT)
        emit CoffeeOrdered(msg.sender, block.timestamp);
    }

    // =========================================================
    // FUNGSI 2: KLAIM PROFIT (INVESTOR)
    // =========================================================
    function claimDividends() external noReentrancy {
        // Cek apakah dia investor
        uint256 holderBalance = assetToken.balanceOf(msg.sender);
        require(holderBalance > 0, "Anda bukan investor");

        // Hitung hak dividen (Logika Matematika)
        uint256 _magnifiedDividendPerShare = magnifiedDividendPerShare;
        int256 _correction = magnifiedDividendCorrections[msg.sender];
        
        uint256 accumulatableDividend = uint256(int256(holderBalance * _magnifiedDividendPerShare) + _correction) / MAGNITUDE;
        uint256 withdrawable = accumulatableDividend - withdrawnDividends[msg.sender];

        require(withdrawable > 0, "Tidak ada profit baru");

        // Update state sebelum transfer (Checks-Effects-Interactions pattern)
        withdrawnDividends[msg.sender] += withdrawable;

        // Transfer profit ke investor
        bool success = paymentToken.transfer(msg.sender, withdrawable);
        require(success, "Gagal kirim profit");

        emit DividendClaimed(msg.sender, withdrawable);
    }

    // Fungsi Pembantu: Dipanggil manual jika investor transfer tokennya ke orang lain
    // (Agar perhitungan dividen pemilik baru tidak error)
    function updateCorrection(int256 _amount) external {
        // Di dunia nyata seharusnya dipanggil otomatis oleh token asset, 
        // tapi untuk demo manual, akan disederhanakan.
        // Logika: Correction += diff * magnifiedDividendPerShare
        // (sementara di skip)
    }

    // =========================================================
    // FUNGSI 3: BAYAR VENDOR (WHITELIST ONLY)
    // =========================================================
    function restockInventory(address _vendor, uint256 _amount) external onlyOwner {
        // Validasi Whitelist: Owner tidak bisa kirim ke sembarang alamat
        require(isWhitelistedVendor[_vendor], "Vendor Ilegal/Tidak Terdaftar!");
        require(paymentToken.balanceOf(address(this)) >= _amount, "Kas kosong");

        bool success = paymentToken.transfer(_vendor, _amount);
        require(success, "Gagal bayar vendor");

        // Menggunakan event baru agar lebih spesifik
        emit RestockPaid(_vendor, _amount);
    }

    // =========================================================
    // FUNGSI 4: VOTING VENDOR BARU (GOVERNANCE)
    // =========================================================
    function proposeNewVendor(address _vendor, string memory _desc) external {
        proposals.push();
        uint256 id = proposals.length - 1;
        Proposal storage p = proposals[id];
        
        p.proposedVendor = _vendor;
        p.description = _desc;
        p.voteCount = 0;
        p.executed = false;
        p.endTime = block.timestamp + 15 minutes; // batas waktu untuk demo
        
        emit ProposalCreated(id, _vendor, _desc);
    }

    function voteProposal(uint256 _id) external {
        // Validasi dasar
        require(_id < proposals.length, "ID Salah");
        Proposal storage p = proposals[_id];
        
        require(block.timestamp < p.endTime, "Waktu voting habis");
        require(!p.executed, "Sudah dieksekusi");
        require(!p.hasVoted[msg.sender], "Sudah vote");

        // Cek berat suara (jumlah token)
        uint256 weight = assetToken.balanceOf(msg.sender);
        require(weight > 0, "Tidak punya token");

        // Catat vote
        p.hasVoted[msg.sender] = true;
        p.voteCount += weight;

        emit Voted(_id, msg.sender, weight);
    }

    function executeProposal(uint256 _id) external {
        require(_id < proposals.length, "ID Salah");
        Proposal storage p = proposals[_id];
        
        require(!p.executed, "Sudah dieksekusi");
        require(block.timestamp >= p.endTime, "Voting belum selesai");

        uint256 totalSupply = assetToken.totalSupply();
        
        // Syarat menang: Lebih dari 50% total supply token setuju
        if (p.voteCount > totalSupply / 2) {
            isWhitelistedVendor[p.proposedVendor] = true;
            p.executed = true;
            emit VendorWhitelisted(p.proposedVendor);
        } else {
            // Jika gagal, tandai executed tapi jangan whitelist (Voting gagal)
            p.executed = true; 
        }
    }

    // --- VIEW FUNCTIONS ---

    function getProposal(uint256 _id) external view returns (
        address proposedVendor, 
        string memory description, 
        uint256 voteCount, 
        bool executed,
        uint256 endTime
    ) {
        require(_id < proposals.length, "ID tidak valid");
        Proposal storage p = proposals[_id];
        return (p.proposedVendor, p.description, p.voteCount, p.executed, p.endTime);
    }

    function getProposalsCount() external view returns (uint256) {
        return proposals.length;
    }
}