// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract VendingMachineDAO {
    
    // =========================================================
    // 1. SETUP KEUANGAN & TOKEN
    // =========================================================
    IERC20 public paymentToken; 
    IERC20 public assetToken; 
    address public owner; 

    uint256 public coffeePrice = 15000 * 10**18; 
    uint256 public cogsPerCup = 5000 * 10**18;   

    uint256 public totalRevenue;
    uint256 public growthFund; 
    uint256 public totalDividendsDistributed;
    uint256 public totalDividendsClaimed;

    // Config
    uint256 public constant REINVEST_RATE = 20; 
    uint256 public constant DIVIDEND_RATE = 80; 
    uint256 constant MAGNITUDE = 2**128;
    
    // ANTI-WHALE CONFIG (Maksimal kepemilikan 40%)
    uint256 public constant MAX_WALLET_PERCENT = 40; 

    // Dividen Tracker
    uint256 public magnifiedDividendPerShare;
    mapping(address => int256) public magnifiedDividendCorrections;
    mapping(address => uint256) public withdrawnDividends;

    uint256 public sharePrice = 1000;

    // =========================================================
    // 2. DATABASE OPERASIONAL
    // =========================================================
    mapping(address => uint256) public staffSalaries;

    struct Machine {
        uint256 id;
        string location;
        bool isActive;
        uint256 totalSales; 
    }
    mapping(uint256 => Machine) public machines; 
    uint256 public machineCount;

    mapping(address => bool) public isWhitelisted;

    // =========================================================
    // 3. SYSTEM DAO (PROPOSAL)
    // =========================================================
    
    enum ProposalType { 
        BUY_MACHINE,    // 0
        BUY_STOCK,      // 1
        UPDATE_SALARY,  // 2
        ADD_VENDOR      // 3
    }

    struct Proposal {
        uint256 id;
        ProposalType pType;
        address target;         
        uint256 amount;         
        string description;     
        uint256 voteCount;
        bool executed;
        uint256 endTime;
        mapping(address => bool) hasVoted;
    }

    mapping(uint256 => Proposal) public proposals;
    uint256 public proposalCount;

    // =========================================================
    // 4. EVENTS & SECURITY
    // =========================================================
    event ProposalCreated(uint256 id, string pType, string desc);
    event ProposalExecuted(uint256 id, bool success);
    event Voted(uint256 proposalId, address voter, uint256 weight);
    
    event CoffeeOrdered(uint256 indexed machineId, address buyer, uint256 amount);
    event ProfitDistributed(uint256 dividendAmount, uint256 growthAmount);
    event SharesPurchased(address investor, uint256 amount, uint256 cost);
    event ShareTransferred(address from, address to, uint256 amount);
    event DividendClaimed(address investor, uint256 amount);
    event ExpensePaid(string category, address to, uint256 amount, string note);

    bool private locked;
    modifier onlyOwner() { require(msg.sender == owner, "Hanya Admin"); _; }
    modifier noReentrancy() { require(!locked, "Reentrancy!"); locked = true; _; locked = false; }

    constructor(address _paymentToken, address _assetToken, uint256 _coffeePrice) {
        paymentToken = IERC20(_paymentToken);
        assetToken = IERC20(_assetToken);
        coffeePrice = _coffeePrice; 
        owner = msg.sender;
        isWhitelisted[msg.sender] = true; 
    }

    // =========================================================
    // BAGIAN A: BISNIS UTAMA (BELI KOPI)
    // =========================================================
    
    function buyCoffee(uint256 _machineId) external noReentrancy {
        require(machines[_machineId].isActive, "Mesin Mati");
        
        uint256 price = coffeePrice; 
        require(paymentToken.transferFrom(msg.sender, address(this), price), "Gagal Bayar");

        machines[_machineId].totalSales += price;
        totalRevenue += price;

        uint256 grossProfit = 0;
        if (price > cogsPerCup) {
            grossProfit = price - cogsPerCup;
        }

        if (grossProfit > 0) {
            uint256 amountGrowth = (grossProfit * REINVEST_RATE) / 100; 
            uint256 amountDividend = (grossProfit * DIVIDEND_RATE) / 100;

            growthFund += amountGrowth;
            totalDividendsDistributed += amountDividend;

            if (assetToken.totalSupply() > 0) {
                magnifiedDividendPerShare += (amountDividend * MAGNITUDE) / assetToken.totalSupply();
                emit ProfitDistributed(amountDividend, amountGrowth);
            }
        }
        emit CoffeeOrdered(_machineId, msg.sender, price);
    }

    // =========================================================
    // BAGIAN B: FITUR ADMIN (OPERASIONAL)
    // =========================================================

    function payMonthlySalary(address _staff) external onlyOwner noReentrancy {
        uint256 salaryAmount = staffSalaries[_staff];
        require(salaryAmount > 0, "Gaji belum diset via Proposal!");
        _processPaymentSmart(_staff, salaryAmount);
        emit ExpensePaid("GAJI BULANAN", _staff, salaryAmount, "Gaji Rutin");
    }

    function addMachine(string memory _loc) external onlyOwner {
        machineCount++;
        machines[machineCount] = Machine(machineCount, _loc, true, 0);
    }

    function setCoffeePrice(uint256 _price) external onlyOwner {
        coffeePrice = _price;
    }

    // =========================================================
    // BAGIAN C: PROPOSAL DAO (HANYA OWNER YANG BISA AJUKAN)
    // =========================================================

    // 1. Proposal Beli Mesin
    function proposeBuyMachine(address _vendor, uint256 _price, string memory _desc) external onlyOwner {
        _createProposal(ProposalType.BUY_MACHINE, _vendor, _price, _desc);
    }

    // 2. Proposal Beli Bahan Baku
    function proposeBuyStock(address _vendor, uint256 _price, string memory _desc) external onlyOwner {
        _createProposal(ProposalType.BUY_STOCK, _vendor, _price, _desc);
    }

    // 3. Proposal Set Gaji Pokok
    function proposeUpdateSalary(address _staff, uint256 _newSalary, string memory _alasan) external onlyOwner {
        _createProposal(ProposalType.UPDATE_SALARY, _staff, _newSalary, _alasan);
    }

    // 4. Proposal Tambah Vendor
    function proposeAddVendor(address _vendor, string memory _nama) external onlyOwner {
        _createProposal(ProposalType.ADD_VENDOR, _vendor, 0, _nama);
    }

    // --- VOTING SYSTEM (Investor tetap harus Vote) ---
    function vote(uint256 _id) external {
        Proposal storage p = proposals[_id];
        require(block.timestamp < p.endTime, "Waktu Habis");
        require(!p.hasVoted[msg.sender], "Sudah Vote");
        uint256 weight = assetToken.balanceOf(msg.sender);
        require(weight > 0, "No Token");
        p.hasVoted[msg.sender] = true;
        p.voteCount += weight;
        emit Voted(_id, msg.sender, weight);
    }

    function executeProposal(uint256 _id) external noReentrancy {
        Proposal storage p = proposals[_id];
        require(!p.executed, "Sudah Dieksekusi");
        require(p.voteCount > assetToken.totalSupply() / 2, "Suara Kurang");

        p.executed = true;

        if (p.pType == ProposalType.BUY_MACHINE) {
            require(isWhitelisted[p.target], "Vendor Ilegal");
            require(growthFund >= p.amount, "Dana Growth Kurang");
            growthFund -= p.amount;
            paymentToken.transfer(p.target, p.amount);
            emit ExpensePaid("BELI MESIN", p.target, p.amount, p.description);

        } else if (p.pType == ProposalType.BUY_STOCK) {
            require(isWhitelisted[p.target], "Vendor Ilegal");
            _processPaymentSmart(p.target, p.amount); 
            emit ExpensePaid("BELI BAHAN", p.target, p.amount, p.description);

        } else if (p.pType == ProposalType.UPDATE_SALARY) {
            staffSalaries[p.target] = p.amount;
            if (!isWhitelisted[p.target]) isWhitelisted[p.target] = true;

        } else if (p.pType == ProposalType.ADD_VENDOR) {
            isWhitelisted[p.target] = true;
        }
        emit ProposalExecuted(_id, true);
    }

    // =========================================================
    // BAGIAN D: INVESTOR (IPO & SAHAM) - DENGAN ANTI-WHALE
    // =========================================================

    // Fungsi Helper untuk Cek Limit 40%
    function _checkMaxWallet(address _user, uint256 _amountToAdd) internal view {
        uint256 totalSupply = assetToken.totalSupply();
        uint256 maxLimit = (totalSupply * MAX_WALLET_PERCENT) / 100;
        uint256 currentBal = assetToken.balanceOf(_user);
        
        require(currentBal + _amountToAdd <= maxLimit, "Max Wallet Limit 40% Reached!");
    }

    function buyShares(uint256 _amount) external noReentrancy {
        uint256 available = assetToken.balanceOf(address(assetToken));
        require(available >= _amount, "Sold Out");

        // CEK ANTI-WHALE (40%)
        _checkMaxWallet(msg.sender, _amount);

        uint256 cost = (_amount * sharePrice);
        
        require(paymentToken.transferFrom(msg.sender, address(this), cost), "Gagal Bayar IDRT");
        require(assetToken.transferFrom(address(assetToken), msg.sender, _amount), "Gagal Kirim Saham");
        
        growthFund += cost; 
        magnifiedDividendCorrections[msg.sender] -= int256(magnifiedDividendPerShare * _amount);
        emit SharesPurchased(msg.sender, _amount, cost);
    }

    function transferSaham(address _to, uint256 _amount) external noReentrancy {
        // CEK ANTI-WHALE (40%) untuk Penerima
        _checkMaxWallet(_to, _amount);

        require(assetToken.transferFrom(msg.sender, _to, _amount), "Gagal Transfer");
        
        int256 corr = int256(magnifiedDividendPerShare * _amount);
        magnifiedDividendCorrections[msg.sender] += corr;
        magnifiedDividendCorrections[_to] -= corr;
        emit ShareTransferred(msg.sender, _to, _amount);
    }

    function claimDividends() external noReentrancy {
        uint256 withdrawable = getWithdrawableDividend(msg.sender);
        require(withdrawable > 0, "Nihil");
        
        withdrawnDividends[msg.sender] += withdrawable;
        totalDividendsClaimed += withdrawable;

        require(paymentToken.transfer(msg.sender, withdrawable), "Gagal");
        emit DividendClaimed(msg.sender, withdrawable);
    }

    // =========================================================
    // HELPER & VIEW
    // =========================================================

    function _createProposal(ProposalType _type, address _target, uint256 _amt, string memory _desc) internal {
        proposalCount++;
        Proposal storage p = proposals[proposalCount];
        p.id = proposalCount;
        p.pType = _type;
        p.target = _target;
        p.amount = _amt;
        p.description = _desc;
        p.endTime = block.timestamp + 1 days; 
        string memory tStr = _type == ProposalType.BUY_MACHINE ? "BELI MESIN" : 
                             _type == ProposalType.BUY_STOCK ? "BELI BAHAN" :
                             _type == ProposalType.UPDATE_SALARY ? "SET GAJI" : "ADD VENDOR";
        emit ProposalCreated(proposalCount, tStr, _desc);
    }

    function _processPaymentSmart(address _target, uint256 _amount) internal {
        uint256 contractBalance = paymentToken.balanceOf(address(this));
        require(contractBalance >= _amount, "Kas Kosong");

        uint256 unclaimedDividends = totalDividendsDistributed - totalDividendsClaimed;
        uint256 lockedFunds = growthFund + unclaimedDividends;
        
        uint256 operationalCash = 0;
        if (contractBalance > lockedFunds) {
            operationalCash = contractBalance - lockedFunds;
        }

        if (operationalCash < _amount) {
            uint256 deficit = _amount - operationalCash;
            require(growthFund >= deficit, "Modal Growth Fund Habis!");
            growthFund -= deficit;
        }
        paymentToken.transfer(_target, _amount);
    }

    // --- VIEW DASHBOARD ---
    
    function getOperationalReserve() external view returns (uint256) {
        uint256 currentBalance = paymentToken.balanceOf(address(this));
        uint256 unclaimedDividends = totalDividendsDistributed - totalDividendsClaimed;
        uint256 lockedFunds = growthFund + unclaimedDividends;

        if (currentBalance > lockedFunds) {
            return currentBalance - lockedFunds;
        }
        return 0;
    }
    
    function getWithdrawableDividend(address _holder) public view returns (uint256) {
        uint256 hb = assetToken.balanceOf(_holder);
        if (hb == 0) return 0;
        int256 acc = int256(hb * magnifiedDividendPerShare);
        int256 corr = magnifiedDividendCorrections[_holder];
        uint256 accumulatable = uint256(acc + corr) / MAGNITUDE;
        uint256 withdrawn = withdrawnDividends[_holder];
        if (accumulatable <= withdrawn) return 0;
        return accumulatable - withdrawn;
    }

    function getAvailableShares() external view returns (uint256) {
        return assetToken.balanceOf(address(assetToken));
    }
}