-- phpMyAdmin SQL Dump
-- version 3.3.2deb1ubuntu1
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Mar 01, 2012 at 04:46 PM
-- Server version: 5.1.41
-- PHP Version: 5.3.2-1ubuntu4.14

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `manager`
--

-- --------------------------------------------------------

--
-- Table structure for table `vmmonitor_vm`
--

CREATE TABLE IF NOT EXISTS `vmmonitor_vm` (
  `instance_id` varchar(50) NOT NULL DEFAULT '',
  `reservation` varchar(50) DEFAULT NULL,
  `user` varchar(50) DEFAULT NULL,
  `dns_name` varchar(50) DEFAULT NULL,
  `private_dns_name` varchar(50) DEFAULT NULL,
  `public_dns_name` varchar(50) DEFAULT NULL,
  `state` varchar(50) DEFAULT NULL,
  `instance_type` varchar(50) DEFAULT NULL,
  `launch_time` varchar(50) DEFAULT NULL,
  `availability_zone` varchar(50) DEFAULT NULL,
  `kernel` varchar(50) DEFAULT NULL,
  `ramdisk` varchar(50) DEFAULT NULL,
  `last_check` varchar(50) DEFAULT NULL,
  `node_hostname` varchar(50) DEFAULT NULL,
  `node_ip` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`instance_id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
