// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/ERC20.sol";
import "https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable.sol";

contract MesinShare is ERC20, Ownable {
    constructor() ERC20("Saham Vending Machine", "MESIN") Ownable(msg.sender) {
        // Supply Tetap (Fixed): Cuma 100 Lembar
        _mint(msg.sender, 100 * 10**18);
    }
}