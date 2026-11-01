-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.2.0                                       //
-- // Date : 2022-10-03                                    //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}votingattributionrule` 
ADD COLUMN `limitValue` int(5) unsigned DEFAULT NULL COMMENT '5';

CREATE TABLE `${prefix}layout` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`idUser` int(12) unsigned NOT NULL COMMENT '12',
`scope` varchar(100) DEFAULT NULL,
`objectClass` varchar(50) DEFAULT NULL,
`isShared` int(1) unsigned DEFAULT '0' COMMENT '1',
`isDefault` int(1) unsigned DEFAULT '0' COMMENT '1',
`sortOrder` int(3) unsigned DEFAULT '0' COMMENT '3',
`comment` mediumtext DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}layoutcolumnselector` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idLayout` int(12) unsigned NOT NULL COMMENT '12',  
`scope` varchar (100) DEFAULT NULL,
`objectClass` varchar(50) DEFAULT NULL,
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`field` varchar(100) DEFAULT NULL,
`attribute` varchar(100) DEFAULT NULL,
`hidden` int(1) unsigned DEFAULT '0' COMMENT '1',
`sortOrder` int(3) unsigned DEFAULT '0' COMMENT '3',
`widthPct` int(3) unsigned DEFAULT '0' COMMENT '3',
`name` varchar(100) DEFAULT NULL,
`subItem` varchar(100) DEFAULT NULL,
`formatter` varchar(100) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}layoutgroup` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12', 
`name` varchar(100) DEFAULT NULL,
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12', 
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}layoutgroupuser` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',  
`idLayoutGroup` int(12) unsigned DEFAULT NULL COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',   
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}layoutforced` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',   
`idLayout` int(12) unsigned NOT NULL COMMENT '12',
`objectClass` varchar(50) DEFAULT NULL,
`idCreator` int(12) unsigned NOT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}employeeleaveearned` ADD `acquisitionStartDate` date;
ALTER TABLE `${prefix}employeeleaveearned` ADD `acquisitionEndDate` date;

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle`, `fonctionName`, `nextTime`) VALUES ('0 * * * *', '../tool/cronExecutionStandard.php 	',1, 'cronBaseline', 	NULL );

INSERT INTO `${prefix}habilitationother` (idProfile, rightAccess, scope) VALUES
(1,1,'canAttributeLayout'),
(3,1,'canAttributeLayout');

DELETE FROM `${prefix}collapsed` WHERE scope like 'Planning_Replan%' or scope like 'Planning_Fixed%' or scope like 'Planning_Construction%';

INSERT INTO `${prefix}indicator` (`id`, `code`, `type`, `name`, `sortOrder`, `idle`) VALUES
(31, 'RWOPW', 'percent', 'RealWorkOverPlannedWork', 270, 0);

INSERT INTO `${prefix}indicatorableindicator` (`idIndicator`, `idIndicatorable`, `nameIndicatorable`, `idle`) VALUES
(31, 2, 'Activity', 0),
(31, 9, 'TestSession', 0),
(31, 8, 'Project', 0);

ALTER TABLE `${prefix}inputmailbox` 
ADD COLUMN `sortOrder` int(3) unsigned DEFAULT 0 COMMENT '3',
ADD COLUMN `actionOK` varchar(10) DEFAULT 'READ',
ADD COLUMN `actionKO` varchar(10) DEFAULT 'READ';

ALTER TABLE `${prefix}providerbill` 
CHANGE `totalUntaxedAmount` `totalUntaxedAmount` DECIMAL(11,2),
CHANGE `totalTaxAmount` `totalTaxAmount` DECIMAL(11,2),
CHANGE `totalFullAmount` `totalFullAmount` DECIMAL(11,2),
CHANGE `untaxedAmount` `untaxedAmount` DECIMAL(11,2),
CHANGE `taxAmount` `taxAmount` DECIMAL(11,2),
CHANGE `fullAmount` `fullAmount` DECIMAL(11,2),
CHANGE `discountFullAmount` `discountFullAmount` DECIMAL(11,2);