// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Import langsung dari OpenZeppelin
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract RupiahToken is ERC20, Ownable {
    constructor() ERC20("Rupiah Digital", "IDRT") Ownable(msg.sender) {
        // Cetak modal awal 1 Juta IDRT (18 desimal)
        _mint(msg.sender, 1_000_000 * 10**18);
    }

    // Fungsi untuk Owner mencetak uang tambahan (misal untuk user lain)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    // Faucet: Siapapun bisa minta 100.000 IDRT (Untuk mempermudah testing)
    function mintaUangGratis() external {
        _mint(msg.sender, 100_000 * 10**18);
    }
}