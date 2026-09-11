-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.4.0                                       //
-- // Date : 2021-10-21                                     //
-- ///////////////////////////////////////////////////////////

INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
('limitDisplayPlanning', 2000),
('coversListPlan','CLOSE'),
('projectSelectorLimitProjectLevel',0);

ALTER TABLE `${prefix}type` 
ADD COLUMN `mandatoryContact` int(1) unsigned DEFAULT 0 COMMENT '1', 
ADD COLUMN `mandatoryRecipient` int(1) unsigned DEFAULT 0 COMMENT '1';

UPDATE `${prefix}type` set `mandatoryContact`=1, `mandatoryRecipient`=1 where scope='Bill';

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDisconnectAll');

CREATE TABLE `${prefix}incomingmail` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`idIncomingMailType` int(12) unsigned DEFAULT NULL COMMENT '12',
`idResponsible` int(12) unsigned DEFAULT NULL COMMENT '12',
`idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`receptionDate` date DEFAULT NULL,
`idDeliveryMode` int(12) unsigned DEFAULT NULL COMMENT '12',
`idProvider` int(12) unsigned DEFAULT NULL COMMENT '12',
`idClient` int(12) unsigned DEFAULT NULL COMMENT '12',
`idContact` int(12) unsigned DEFAULT NULL COMMENT '12',
`descriptionTransmitter` mediumtext DEFAULT NULL,
`description` mediumtext DEFAULT NULL,
`idApprovalStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}outgoingmail` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`idOutgoingMailType` int(12) unsigned DEFAULT NULL COMMENT '12',
`sendDate` date DEFAULT NULL,
`idDeliveryMode` int(12) unsigned DEFAULT NULL COMMENT '12',
`idResponsible` int(12) unsigned DEFAULT NULL COMMENT '12',
`idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`idProvider` int(12) unsigned DEFAULT NULL COMMENT '12',
`idClient` int(12) unsigned DEFAULT NULL COMMENT '12',
`idContact` int(12) unsigned DEFAULT NULL COMMENT '12',
`address` varchar(200) DEFAULT NULL,
`descriptionRecipient` mediumtext DEFAULT NULL,
`description` mediumtext DEFAULT NULL,
`idApprovalStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(270, 'menuOutgoingMail', 7, 'object', 155, 'Project', 0, 'Work '),
(271, 'menuIncomingMail', 7, 'object', 160, 'Project', 0, 'Work '),
(272, 'menuIncomingMailType', 79, 'object', 997, 'ReadWriteType', 0, 'Type'),
(273, 'menuOutgoingMailType', 79, 'object', 998, 'ReadWriteType', 0, 'Type');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`,`moduleName`) VALUES
(357,'navMailNavigation',5,0,110,0,'moduleMail'),
(358,'menuOutgoingMail',357,270,115,0,'moduleMail'),
(359,'menuIncomingMail',357,271,120,0,'moduleMail'),
(360,'menuIncomingMailType',330,272,999,0,'moduleMail'),
(361,'menuOutgoingMailType',330,273,998,0,'moduleMail');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 270, 1),
(2, 270, 1),
(3, 270, 1),
(1, 271, 1),
(2, 271, 1),
(3, 271, 1),
(1, 272, 1),
(1, 273, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 270, 8),
(2, 270, 8),
(3, 270, 8),
(1, 271, 8),
(2, 271, 8),
(3, 271, 8),
(1, 272, 8),
(2, 272, 8),
(3, 272, 8),
(1, 273, 8),
(2, 273, 8),
(3, 273, 8);

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`) VALUES 
(29,'moduleMail','750',10,0,0); 

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(210,29,270,0,0),
(211,29,271,0,0),
(212,29,272,0,0),
(213,29,273,0,0);

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('IncomingMail', 'postal mail', 10, 1, 0),
('IncomingMail', 'email', 20, 1, 0),
('IncomingMail', 'service note', 30, 1, 0),
('OutgoingMail', 'postal mail', 10, 1, 0),
('OutgoingMail', 'email', 20, 1, 0),
('OutgoingMail', 'service note', 30, 1, 0);