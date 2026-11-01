-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.2.0                                       //
-- // Date : 2021-06-15                                     //
-- ///////////////////////////////////////////////////////////



INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
('activityOnRealTime','NO'),
('showDonePlannedWork','1'),
('notStartBeforeValidatedStartDate','NO');

ALTER TABLE `${prefix}type` ADD COLUMN `activityOnRealTime` int(1) unsigned DEFAULT 0 COMMENT '1';

ALTER TABLE `${prefix}activity` ADD COLUMN `workOnRealTime` int(1) unsigned DEFAULT 0 COMMENT '1';

CREATE TABLE `${prefix}statusperiod` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
`active` int(1) unsigned DEFAULT NULL COMMENT '1',
`type` varchar(10) DEFAULT NULL,
`startDate` datetime DEFAULT NULL,
`endDate` datetime DEFAULT NULL,
`idStatusStart` int(12) unsigned DEFAULT NULL COMMENT '12',
`idStatusEnd` int(12) unsigned DEFAULT NULL COMMENT '12',
`idUserStart` int(12) unsigned DEFAULT NULL COMMENT '12',
`idUserEnd` int(12) unsigned DEFAULT NULL COMMENT '12',
`duration` varchar(100) DEFAULT NULL,
`durationOpenTime` varchar(100) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}habilitationother` (idProfile, scope , rightAccess)
SELECT id , 'canWorkOnTicket', '1' from `${prefix}profile` where id in (SELECT idProfile from `${prefix}habilitationother` where scope = 'work' and rightAccess='4');

INSERT INTO `${prefix}habilitationother` (idProfile, scope , rightAccess)
SELECT id , 'canWorkOnTicket', '2' from `${prefix}profile` where id in (SELECT idProfile from `${prefix}habilitationother` where scope = 'work' and rightAccess <> '4');

UPDATE `${prefix}status` set setHandledStatus='1' where name='paused';

ALTER TABLE `${prefix}delay` ADD `idMacroStatus` int(12) unsigned DEFAULT 2 COMMENT '12';

ALTER TABLE `${prefix}project` ADD `startAM` time DEFAULT NULL, 
							   ADD `endAM` time DEFAULT NULL,
							   ADD `startPM` time DEFAULT NULL,
							   ADD `endPM` time DEFAULT NULL;

CREATE TABLE `${prefix}activityworkunit` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
`idWorkUnit` int(12) unsigned DEFAULT NULL COMMENT '12',
`idComplexity` int(12) unsigned DEFAULT NULL COMMENT '12',
`quantity` decimal(8,3) unsigned DEFAULT NULL,
`idWorkCommand` INT(12) DEFAULT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}activityworkunit` (refType, refId, idWorkUnit, idComplexity , quantity , idWorkCommand)
SELECT refType, refId, idWorkUnit, idComplexity , quantity , idWorkCommand
FROM `${prefix}planningelement` WHERE idWorkUnit is not null and idComplexity is not null and quantity is not null;

ALTER TABLE `${prefix}planningelement` ADD COLUMN `hasWorkUnit` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `hasWorkUnit` int(1) unsigned DEFAULT 0 COMMENT '1';

ALTER TABLE `${prefix}workcommanddone` ADD COLUMN `idActivityWorkUnit` int(12) unsigned DEFAULT NULL COMMENT '12';

UPDATE `${prefix}planningelement` SET hasWorkUnit=1 
WHERE `idWorkUnit` is not null and `idComplexity` is not null and `quantity` is not null;

DELETE FROM `${prefix}workcommanddone` WHERE 1=1;

INSERT INTO `${prefix}workcommanddone` (idWorkCommand, refType, refId , doneQuantity, idActivityWorkUnit )
SELECT idWorkCommand, refType, refId , quantity, id
FROM `${prefix}activityworkunit` 
WHERE idWorkCommand is not null;

ALTER TABLE `${prefix}planningelement` DROP COLUMN `idWorkUnit`;
ALTER TABLE `${prefix}planningelement` DROP COLUMN `idComplexity`;
ALTER TABLE `${prefix}planningelement` DROP COLUMN `quantity`;
ALTER TABLE `${prefix}planningelement` DROP COLUMN `idWorkCommand`;
ALTER TABLE `${prefix}planningelementbaseline` DROP COLUMN `idWorkUnit`;
ALTER TABLE `${prefix}planningelementbaseline` DROP COLUMN `idComplexity`;
ALTER TABLE `${prefix}planningelementbaseline` DROP COLUMN `quantity`;
ALTER TABLE `${prefix}planningelementbaseline` DROP COLUMN `idWorkCommand`;

ALTER TABLE `${prefix}ticket` ADD COLUMN `paused` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}ticket` ADD COLUMN `pausedDateTime` datetime DEFAULT NULL;

ALTER TABLE `${prefix}type` ADD COLUMN `lockPaused` int(1) unsigned DEFAULT 0 COMMENT '1';

--acces right to repository

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(258, 'menuDocumentRight', 37, 'item', 1275, Null, 0, 'HabilitationParameter ');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(338,'menuDocumentRight',130,258,85,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1,258,1),
(2,258,1),
(3,258,1);

ALTER TABLE `${prefix}documentdirectory` ADD COLUMN `idResource` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}documentdirectory` ADD COLUMN `idUser` int(12) unsigned DEFAULT NULL COMMENT '12';
CREATE INDEX `documentdirectoryResource` ON `${prefix}documentdirectory` (`idResource`);
CREATE INDEX `documentdirectoryUser` ON `${prefix}documentdirectory` (`idUser`);
UPDATE `${prefix}documentdirectory` set idUser=(select min(id) from `${prefix}resource`);
UPDATE `${prefix}menu` set level='ReadWritePrincipal' where id=103;

CREATE TABLE `${prefix}documentright` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idDocumentDirectory` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idProfile` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idAccessMode` int(12)  unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;


INSERT INTO `${prefix}documentright` (idDocumentDirectory, idProfile , idAccessMode)
SELECT d.id, p.id, a.idAccessProfile FROM `${prefix}documentdirectory` as d CROSS JOIN `${prefix}profile` as p INNER JOIN `${prefix}accessright` as a ON p.id = a.idProfile and a.idMenu=102;

UPDATE `${prefix}type` set lockPaused=lockDone where scope='Ticket';

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`) VALUES
(119, 'reportTicketHandledMonthSynthesis',3, 'ticketHandledMonthSynthesis.php', 396,'1'),
(120, 'reportTicketDoneMonthSynthesis',3, 'ticketDoneMonthSynthesis.php', 397,'1'),
(121, 'reportYearlyResourcePlan',2, 'yearlyResourcePlan.php', 245,'0'),
(122, 'reportYearlyPlanResource',2, 'yearlyPlanResource.php', 251,'0'),
(123, 'reportSynthesisOrdersInvoiceClient',7, 'synthesisOrdersInvoiceClient.php', 770,'0');



INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 119, 1),
(1, 120, 1),
(1, 121, 1),
(1, 122, 1),
(1, 123, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(119, 'idProject', 'projectList', 10, 'currentProject'),
(119,'idTicketType','ticketType',15,null),
(119, 'month', 'month', 20,'currentMonth'),
(119,'issuer','userList',25,null),
(119, 'requestor', 'requestorList', 30, null),
(119,'responsible','resourceList',35,null),
(119,'ticketWithoutDelay','boolean',40,null),
(120, 'idProject', 'projectList', 10, 'currentProject'),
(120,'idTicketType','ticketType',15,null),
(120, 'month', 'month', 20,'currentMonth'),
(120,'issuer','userList',25,null),
(120, 'requestor', 'requestorList', 30, null),
(120,'responsible','resourceList',35,null),
(120,'ticketWithoutDelay','boolean',40,null),
(121, 'idProject', 'projectList', 10, 'currentProject'),
(121, 'idOrganization', 'organizationList', 20,null),
(121,'idTeam','teamList',30,null),
(121, 'year', 'year', 40,'currentYear'),
(122, 'idProject', 'projectList', 10, 'currentProject'),
(122, 'idOrganization', 'organizationList', 20,null),
(122,'idTeam','teamList',30,null),
(122, 'year', 'year', 40,'currentYear'),
(123, 'idProject', 'projectList', 10, 'currentProject'),
(123,'idClient','clientList',20,null),
(123,'showClosedItems','boolean',30,null),
(123,'showReference','boolean',40,null);


INSERT INTO `${prefix}modulereport` (`idModule`,`idReport`,`hidden`,`active`) VALUES
(2,119,0,1),
(2,120,0,1),
(1,121,0,1),
(1,122,0,1),
(7,123,0,1);

CREATE TABLE `${prefix}macrostatus` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}macrostatus` (`id`,`name`) VALUES
(1,'macroStatusHandled'),
(2,'macroStatusDone'),
(3,'macroStatusIdle');

-- Fix issue for 
DELETE FROM `${prefix}accessright` where idMenu=222;

ALTER TABLE `${prefix}subtask` CHANGE `name` `name` varchar(4000);

ALTER TABLE ${prefix}workcommanddone CHANGE `doneQuantity` `doneQuantity` decimal(8,3);
ALTER TABLE ${prefix}workcommandbilled CHANGE `billedQuantity` `billedQuantity` decimal(8,3);
ALTER TABLE ${prefix}workcommand CHANGE `commandQuantity` `commandQuantity` decimal(8,3);
ALTER TABLE ${prefix}workcommand CHANGE `doneQuantity` `doneQuantity` decimal(8,3);
ALTER TABLE ${prefix}workcommand CHANGE `billedQuantity` `billedQuantity` decimal(8,3);
ALTER TABLE ${prefix}workcommand CHANGE `unitAmount` `unitAmount` decimal(14,2);
ALTER TABLE ${prefix}workcommand CHANGE `commandAmount` `commandAmount` decimal(14,2);
ALTER TABLE ${prefix}workcommand CHANGE `doneAmount` `doneAmount` decimal(14,2);
ALTER TABLE ${prefix}workcommand CHANGE `billedAmount` `billedAmount` decimal(14,2);

-- Access rights on assets

ALTER TABLE `${prefix}asset` ADD COLUMN `idResource` int(12) unsigned DEFAULT NULL COMMENT '12';

-- PERFOMANCE IMPROVMENTS

CREATE TABLE `${prefix}kpivaluerequest` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12) unsigned DEFAULT NULL COMMENT '12',
  `requestDate` date,
  `requestDateTime` datetime,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `kpivaluerequestReference` ON `${prefix}kpivalue` (`refType`, `refId`);

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('01 * * * *', '../tool/cronExecutionStandard.php', 0, 'kpiCalculate');

INSERT INTO `${prefix}parameter` (idUser, idProject, parameterCode, parameterValue) VALUES
(null,null, 'paramTryToHackObjectMail', 'Try to hack detected');

-- ======================================
-- Poker Session
-- ======================================

CREATE TABLE `${prefix}pokercomplexity` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `value` int(3) unsigned DEFAULT NULL COMMENT '3',
  `work` decimal(9,5) unsigned DEFAULT NULL,
  `sortOrder` int(3) unsigned DEFAULT NULL COMMENT '3',
  `idle` int(1) unsigned DEFAULT 0 COMMENT '1',
  `idleDate` datetime DEFAULT NULL,
  `color` varchar(7) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}pokersession` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `pokerSessionDate` date DEFAULT NULL,
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(2) unsigned DEFAULT NULL COMMENT '2',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idPokerSessionType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `attendees` varchar(4000) DEFAULT NULL,
  `pokerSessionStartTime` time DEFAULT NULL,
  `pokerSessionEndTime` time DEFAULT NULL,
  `pokerSessionStartDateTime` datetime DEFAULT NULL,
  `pokerSessionEndDateTime` datetime DEFAULT NULL,
  `handled` int(1) unsigned DEFAULT 0 COMMENT '1',
  `handledDate` datetime DEFAULT NULL,
  `done` int(1) unsigned DEFAULT 0 COMMENT '1',
  `doneDate` datetime DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT 0 COMMENT '1',
  `idleDate` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}pokerresource` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idPokerSession` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}pokeritem` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idPokerSession` int(12) unsigned DEFAULT NULL COMMENT '12',
  `value` varchar(100) DEFAULT NULL,
  `work` decimal(9,5) unsigned DEFAULT NULL,
  `isOpen` int(1) unsigned DEFAULT 0 COMMENT '1',
  `comment` varchar(4000) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}pokervote` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idPokerItem` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idPokerSession` int(12) unsigned DEFAULT NULL COMMENT '12',
  `value` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(259, 'menuPokerSession', 7, 'object', 155, 'Project', 0, 'Work '),
(260, 'menuPokerSessionVoting', 7, 'object', 160, 'Project', 0, 'Work '),
(268, 'menuPokerSessionType', 79, 'object', 981, 'ReadWriteType', 0, 'Type'),
(269, 'menuPokerComplexity',36,'object', 900,'ReadWriteList',0,'ListOfValues');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(339,'menuPokerSession',3,259,115,0),
(340,'menuPokerSessionVoting',3,260,120,0),
(351,'menuPokerSessionType',132,268,45,0),
(352,'menuPokerComplexity',322,269,155,0);

INSERT INTO `${prefix}pokercomplexity` (`name`, `value`, `work`,`sortOrder`,`color`) VALUES
('1', 1, 0.5, 10, '#a2a2c3'),
('2', 2, 1, 20, '#a2a2c3'),
('3', 3, 1.5, 30, '#a2a2c3'),
('5', 5, 2.5, 40, '#a2a2c3'),
('8', 8, 4, 50, '#a2a2c3'),
('13', 13, 6.5, 60, '#a2a2c3'),
('20', 20, 10, 70, '#a2a2c3'),
('40', 40, 20, 80, '#a2a2c3'),
('60', 60, 30, 90, '#a2a2c3'),
('100', 100, 50, 100, '#a2a2c3'),
('?', null, 0, 110, '#f1a874');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('PokerSession', 'live session', 10, 1, 0),
('PokerSession', 'session with due date voting', 20, 1, 0);

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`) VALUES 
(22,'modulePoker','110',null,1,0); 

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(198,22,259,0,0),
(199,22,260,0,0),
(200,22,268,0,0),
(201,22,269,0,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 259, 1),
(2, 259, 1),
(3, 259, 1),
(1, 268, 1),
(2, 268, 0),
(3, 268, 0),
(1, 269, 1),
(2, 269, 0),
(3, 269, 0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT id , 260,1 from `${prefix}profile`;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 259, 8),
(2, 259, 2),
(3, 259, 7),
(1, 260, 4),
(2, 260, 3),
(3, 260, 3),
(4, 260, 3),
(5, 260, 3),
(6, 260, 3),
(7, 260, 3),
(1, 268, 8),
(1, 269, 8);

ALTER TABLE `${prefix}workunit` ADD COLUMN `idle` int(1) unsigned DEFAULT 0 COMMENT '1';

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronCloseMails'),
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDeleteMails'),
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronCloseAlerts'),
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDeleteAlerts'),
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDeleteNotifications'),
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronDeleteAudit');

ALTER TABLE `${prefix}navigation` ADD COLUMN `moduleName` varchar(100) DEFAULT NULL;
UPDATE `${prefix}navigation` SET moduleName='moduleTicket' WHERE name='navTicketing';
UPDATE `${prefix}navigation` SET moduleName='moduleRisk' WHERE name='navRiskManagement';

-- ======================================
-- Localization module
-- ======================================

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(261,'menuLocalization',0,'menu', 476,null,0,'Localization'),
(262,'menuLocalizationRequest',261,'object', 477,'ReadWriteLocalization',0,'Localization'),
(263,'menuLocalizationItem',261,'object', 477,'ReadWriteLocalization',0,'Localization'),
(264,'menuLocalizationTranslator',261,'object', 477,'ReadWriteLocalization',0,'Localization');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,261,1),
(1,262,1),
(1,263,1),
(1,264,1),
(2,261,1),
(2,262,1),
(2,263,1),
(2,264,1),
(3,261,1),
(3,262,1),
(3,263,1),
(3,264,1),
(4,261,1),
(4,262,1),
(4,263,1),
(4,264,0);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1,262,1000001),
(1,263,1000001),
(1,264,1000001),
(2,262,1000002),
(2,263,1000002),
(2,264,1000002),
(3,262,1000001),
(3,263,1000001),
(4,262,1000001),
(4,263,1000001);

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`) VALUES 
(21,'moduleLocalization','880',null,0,0);

INSERT INTO `${prefix}modulemenu` (`idModule`,`idMenu`,`hidden`,`active`) VALUES
(21,262,0,0),
(21,263,0,0),
(21,264,0,0);

CREATE TABLE `${prefix}localizationtranslator` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}localizationtranslatorlanguage` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idTranslator` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLanguage` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLanguageSkillLevel` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `creationDate` date DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}languageskilllevel` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `color` varchar(7) DEFAULT NULL,
  `sortOrder` int(3) unsigned DEFAULT NULL COMMENT '3',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES 
(265, 'menuLanguageSkillLevel',36,'object',896,'ReadWriteList',0, 'ListOfValues');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,265,1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1,265,1000001);

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(266, 'menuLocalizationRequestType', 79, 'object', 1042, 'ReadWriteType', 0, 'Type');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,266,1);

CREATE TABLE `${prefix}localizationrequest` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `textToTranslate` mediumtext,
  `context` mediumtext,
  `localizationId` VARCHAR(100) DEFAULT NULL,
  `idLocalizationRequestType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLocalizationItemType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLanguage` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLocalizationTranslator` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProductVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponentVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idActivity` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAccountable` int(12) unsigned DEFAULT NULL COMMENT '12',
  `plannedDeliveryDate` date DEFAULT NULL,
  `realDeliveryDate` date DEFAULT NULL,
  `creationDateTime` DATETIME DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}type` ADD  `idStatus` int(12) unsigned DEFAULT NULL;

CREATE TABLE `${prefix}localizationitem` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `localizationId` varchar(100) DEFAULT NULL,
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLocalizationRequest` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLocalizationItemType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLocalizationTranslator` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idLanguage` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idOriginLanguage` int(12) unsigned DEFAULT NULL COMMENT '12',
  `textToTranslate` mediumtext,
  `actualDueDate` date DEFAULT NULL,
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `context` mediumtext,
  `idProductVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponentVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `localizationResult` mediumtext,
  `automaticProcess` int(1) unsigned DEFAULT '0' COMMENT '1',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(267, 'menuLocalizationItemType', 79, 'object', 1043, 'ReadWriteType', 0, 'Type');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,267,1);

INSERT INTO `${prefix}mailable` (`id`, `name`, `idle`) VALUES
(45, 'LocalizationItem', 0),
(46, 'LocalizationRequest', 0);

ALTER TABLE `${prefix}type` ADD  `numberDaysBeforeDueDate` int(6) unsigned DEFAULT NULL COMMENT '6';

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(341,'navLocalization',0,0,95,0),
(342,'menuLocalizationRequest',341,262,20,0),
(343,'menuLocalizationItem',341,263,30,0),
(344,'menuLocalizationTranslator',341,264,40,0),
(345, 'menuLanguageSkillLevel',354,265,30,0),
(346, 'menuLocalizationRequestType',332,266,60,0),
(347, 'menuLocalizationItemType', 332,267,70,0),
(348, 'menuLanguageSkillLevel',341,265,50,0),
(349, 'menuLocalizationRequestType',341,266,60,0),
(350, 'menuLocalizationItemType',341,267,70,0),
(353, 'menuEmployee',112,212,65,0),
(354,'navLocalization',131,0,110,0),
(355,'menuLanguage',341,178,45,0);

UPDATE `${prefix}navigation` set idParent=354, sortOrder=10 where id=199;
UPDATE `${prefix}navigation` SET moduleName='moduleLocalization' WHERE id=341;

INSERT INTO `${prefix}modulemenu` (`idModule`,`idMenu`,`hidden`,`active`) VALUES
(21,265,0,0),
(21,266,0,0),
(21,267,0,0);

INSERT INTO `${prefix}languageskilllevel` (`id`,`name`,`color`,`sortOrder`,`idle`) VALUES
(1, 'beginner','#ff0000',10,0),
(2, 'intermediate','#ffa500',20,0),
(3, 'advanced','#00ff00',30,0);

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`, `idStatus`) VALUES 
('LocalizationRequest', 'standard translation',10,1, 0, 1),
('LocalizationRequest', 'urgent translation',20,1, 0, 1),
('LocalizationItem', 'item',10,1, 0, 1);

INSERT INTO `${prefix}eventformail` (`id`, `name`, `idle`, `sortOrder`) VALUES
(15, 'priorityChanged', 0, 105),
(16, 'newUserCreated', 0, 110);
INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
( 'paramMailTitlePriorityChanged', '[${dbName}] Priority change on ticket #${id}'),
( 'paramMailTitleNewUserCreated', '[${dbName}] The user #${id} has been created');
INSERT INTO `${prefix}mailable` (name, `idle`) VALUES 
('User', 0);

UPDATE `${prefix}report` set sortOrder=125 where id=3 ;
UPDATE `${prefix}report` set sortOrder=905 where id=25 ;
UPDATE `${prefix}report` set sortOrder=915 where id=24 ;
UPDATE `${prefix}report` set sortOrder=855 where id=88 ;

UPDATE `${prefix}navigation` set idParent=13, sortOrder=110 where id=69 ;
UPDATE `${prefix}navigation` set idParent=14, sortOrder=110 where id=70;

-- Patchs IGE
ALTER TABLE `${prefix}message` ADD `idOrganization` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}message` ADD `idTeam` int(12) unsigned DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`) VALUES
(1, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(2, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(3, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(28, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(29, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(30, 'idActivityType', 'activityTypeList', 7, 0, NULL, 0),
(40, 'idActivityType', 'activityTypeList', 30, 0, NULL, 0),
(111, 'idActivityType', 'activityTypeList', 30, 0, NULL, 0),
(112, 'idActivityType', 'activityTypeList', 23, 0, NULL, 0),
(113, 'idActivityType', 'activityTypeList', 23, 0, NULL, 0),
(114, 'idActivityType', 'activityTypeList', 23, 0, NULL, 0);

CREATE INDEX indicatorvalueType ON `${prefix}indicatorvalue` (type,idle);