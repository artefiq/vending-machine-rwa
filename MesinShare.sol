// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MesinShare is ERC20, Ownable {
    
    // Kita simpan alamat Vending Machine yang dipercaya
    address public vendingMachine;

    constructor() ERC20("Saham Vending Machine", "MESIN") Ownable(msg.sender) {
        // PERUBAHAN 1: Mint ke alamat kontrak ini sendiri (Gudang), bukan ke msg.sender
        _mint(address(this), 100000 * 10**18);
    }

    // PERUBAHAN 2: Fungsi untuk mendaftarkan Vending Machine
    function setVendingMachine(address _vendingMachine) external onlyOwner {
        vendingMachine = _vendingMachine;

        // Izin untuk mengirim token
        _approve(address(this), _vendingMachine, balanceOf(address(this)));
    }
}