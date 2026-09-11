-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.3.0                                       //
-- // Date : 2021-06-15                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}pokeritem` ADD `flipped` int(1) DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}pokersession` ADD `description` mediumtext DEFAULT NULL;
ALTER TABLE `${prefix}pokersession` ADD `result` mediumtext DEFAULT NULL;
ALTER TABLE `${prefix}pokersession` ADD `idUser` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}pokersession` CHANGE `handledDate` `handledDate` date;
ALTER TABLE `${prefix}pokersession` CHANGE `doneDate` `doneDate` date;
ALTER TABLE `${prefix}pokersession` CHANGE `idleDate` `idleDate` date;
ALTER TABLE `${prefix}pokersession` CHANGE `idResource` `idResource` int(12) COMMENT '12';
ALTER TABLE `${prefix}pokercomplexity` CHANGE `work` `itemWork` DECIMAL(9,5) UNSIGNED NULL DEFAULT NULL;
UPDATE `${prefix}module` SET idle='0' WHERE name='modulePoker';

UPDATE `${prefix}menu` SET sortOrder=901 WHERE name='menuType';
UPDATE `${prefix}menu` SET sortOrder=156 WHERE name='menuPokerSessionVoting';
UPDATE `${prefix}menu` SET sortOrder=121 WHERE name='menuPlannedWorkManual';
UPDATE `${prefix}menu` SET sortOrder=122 WHERE name='menuViewAllSubTask';
UPDATE `${prefix}menu` SET sortOrder=148 WHERE name='menuReports';
UPDATE `${prefix}menu` SET sortOrder=478 WHERE name='menuLocalizationItem';
UPDATE `${prefix}menu` SET sortOrder=479 WHERE name='menuLocalizationTranslator';
UPDATE `${prefix}menu` SET sortOrder=962 WHERE name='menuInvoiceType';


ALTER TABLE `${prefix}pokerresource` ADD `idAssignment` int(12) unsigned DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}planningmode` (name, code, sortOrder, mandatoryStartDate, mandatoryEndDate, applyTo, idle, mandatoryDuration) VALUES 
('PlanningModeFIXED', 'FIXED', 100, 1, 0, 'PokerSession', 0, 0);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(4, 259, 9),
(5, 259, 9),
(6, 259, 9),
(7, 259, 9);

UPDATE `${prefix}navigation` SET moduleName='modulePlanning' WHERE name='navPlanning';
UPDATE `${prefix}navigation` SET moduleName='moduleReview' WHERE name='navSteering';

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(356,'menuKanban',17,100006001,85,50);

CREATE TABLE `${prefix}highlight` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`scope` varchar(100) DEFAULT NULL,
`date` date,
`reference` varchar(100) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDeleteLogfile');

--Module 
ALTER TABLE `${prefix}module` ADD `parentActive` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}module` ADD `notActiveAlone` int(1) unsigned DEFAULT 0 COMMENT '1';

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`) VALUES 
(23,'moduleTargetMilestone','112',1,0,0),
(24,'moduleTechnicalProgress','114',1,0,0),  
(25,'moduleFollowUp','300',null,0,(SELECT `active` from `${prefix}module` as m WHERE m.name='moduleImputation' )),
(26,'moduleBudgetFunctionOfOrga','1110',14,0,0), 
(27,'moduleTodoList','320',25,0,0), 
(28,'moduleChecklist','330',25,0,0);

UPDATE `${prefix}module` SET idModule=1, sortOrder=110, parentActive=1 WHERE name ='moduleMeeting';
UPDATE `${prefix}module` SET idModule=1, sortOrder=120 WHERE name ='modulePoker';
UPDATE `${prefix}module` SET idModule=10, sortOrder=720 WHERE name='moduleAssets';
UPDATE `${prefix}module` SET idModule=10, sortOrder=730, parentActive=1 WHERE name='moduleRisk';
UPDATE `${prefix}module` SET idModule=10, sortOrder=740, parentActive=1 WHERE name='moduleRequirement';
UPDATE `${prefix}module` SET idModule=25, sortOrder=310, parentActive=1 WHERE name='moduleImputation';
UPDATE `${prefix}module` SET parentActive=1 WHERE name in ('moduleExpenses','moduleIncomes');
UPDATE `${prefix}module` SET notActiveAlone=1 WHERE name in ('moduleFinancial','moduleFollowUp');

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(208,27,257,0,0),
(209,28,130,0,0);

CREATE INDEX historyarchiveRef ON `${prefix}historyarchive` (`refType`, `refId`);

ALTER TABLE `${prefix}messagelegal` 
ADD `idProfile` INT(12) UNSIGNED NULL DEFAULT NULL COMMENT '12',
ADD `idProject` INT(12) UNSIGNED NULL DEFAULT NULL COMMENT '12',
ADD `idOrganization` INT(12) UNSIGNED NULL DEFAULT NULL COMMENT '12',
ADD `idTeam` INT(12) UNSIGNED NULL DEFAULT NULL COMMENT '12',
ADD `idAffectable` INT(12) UNSIGNED NULL DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}copyable` (`id`,`name`, `idle`, `sortOrder`,`idDefaultCopyable`) VALUES 
(32,'SubTask', '1', '920','1');

ALTER TABLE `${prefix}command` ADD `idRecipient` int(12) unsigned DEFAULT NULL COMMENT '12';

ALTER TABLE `${prefix}inputmailbox` 
ADD `autoclosedReason` varchar(200) DEFAULT NULL,
ADD `autoclosedDateTime` datetime DEFAULT NULL;

INSERT INTO `${prefix}notifiable` (notifiableitem, name, idle) VALUES 
('InputMailbox', 'InputMailbox',0);