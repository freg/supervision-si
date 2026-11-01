-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.1.0                                      //
-- // Date : 2025-01-03                                     //
-- ///////////////////////////////////////////////////////////

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`, `isLeavesSystemMenu`)VALUES
(314, 'menuPlanningWorkPlan', '7', 'item', '154', NULL, '0', 'Work ', '0', '0');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `tag`) VALUES 
(410, 'menuPlanningWorkPlan', '1', '314', '0', '72', 'gantt'),
(411, 'menuPlanningWorkPlan', '10', '314', '0', '111', 'gantt');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1, 314, 1),
(2, 314, 1),
(3, 314, 1),
(4, 314, 1),
(6, 314, 1),
(7, 314, 1),
(5, 314, 1);

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`) VALUES
('1', '314', '0', '1');

CREATE TABLE `${prefix}inputmailboximport` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(200) DEFAULT NULL,
  `serverImap` varchar(200) DEFAULT NULL,
  `imapUserAccount` varchar(200) DEFAULT NULL,
  `pwdImap` varchar(50) DEFAULT NULL,
  `idAffectable` int(12) unsigned COMMENT '12',
  `lastInputDate` datetime DEFAULT NULL ,
  `failedRead` int(1) unsigned DEFAULT '0' COMMENT '1',
  `failedMessage` int(1) unsigned DEFAULT '0' COMMENT '1',
  `limitOfHistory` int(6) unsigned DEFAULT '0' COMMENT '6',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  `idleDate` date DEFAULT NULL,
  `autoclosedReason` varchar(200) DEFAULT NULL,
  `autoclosedDateTime`  datetime DEFAULT NULL,
  `limitOfInputPerHourImport` int(6) unsigned DEFAULT '0' COMMENT '6',
  `sortOrder` int(3) unsigned DEFAULT 0 COMMENT '3',
  `actionOK` varchar(10) DEFAULT 'READ',
  `actionKO` varchar(10) DEFAULT 'READ',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(315,'menuInputMailboxImport',88,'object', 694,'Project',0,'Automation');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 315, 1),
(2, 315, 1),
(3, 315, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 315, 8),
(2, 315, 2),
(3, 315, 7);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(409,'menuInputMailboxImport',129,315,989,0);

ALTER TABLE `${prefix}inputmailboxhistory` ADD `refType` varchar(100);

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronReorderWBS');

RENAME TABLE  ${prefix}inputmailbox TO ${prefix}inputmailboxticket;
UPDATE `${prefix}menu` SET `name` = 'menuInputMailboxTicket' WHERE `name` = 'menuInputMailbox';
UPDATE `${prefix}navigation` SET `name` = 'menuInputMailboxTicket' WHERE `name` = 'menuInputMailbox';

-- MySql Compatibility
ALTER TABLE `${prefix}assignment` CHANGE `manual` `isManual` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}work` CHANGE `manual` `isManual` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}plannedwork` CHANGE `manual` `isManual` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}plannedworkbaseline` CHANGE `manual` `isManual` int(1) unsigned DEFAULT '0' COMMENT '1';

ALTER TABLE `${prefix}subtask` ADD `dueDate` date DEFAULT NULL;

ALTER TABLE `${prefix}cronautosendreport` CHANGE `reportParameter` `reportParameter` varchar(4000) DEFAULT NULL;

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `required`) VALUES 
(59, 'filterActivity', 'filterActivityInput', 45, '', 0);


INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
('sizeAttachmentInputMails','5');