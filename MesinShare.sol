// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MesinShare is ERC20, Ownable {
    constructor() ERC20("Saham Vending Machine", "MESIN") Ownable(msg.sender) {
        // Supply Tetap (Fixed): Cuma 100 Lembar
        _mint(msg.sender, 100 * 10**18);
    }
}