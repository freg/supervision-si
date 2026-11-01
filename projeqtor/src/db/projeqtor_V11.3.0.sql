-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.3.0                                      //
-- // Date : 2024-04-05                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}lessonlearned` ADD COLUMN `idResource` int(12) unsigned DEFAULT NULL;

DELETE FROM `${prefix}cronautosendreport` WHERE idReport=49;
DELETE FROM `${prefix}cronautosendreport` WHERE idReport=7;

DELETE FROM `${prefix}today` WHERE idReport=49;
DELETE FROM `${prefix}today` WHERE idReport=7;

DELETE FROM `${prefix}report` WHERE name='reportPlanGantt';
DELETE FROM `${prefix}report` WHERE name='reportPortfolioGantt';

DELETE FROM `${prefix}favorite` WHERE idReport=49;
DELETE FROM `${prefix}favorite` WHERE idReport=7;

DELETE FROM `${prefix}favoriteparameter` WHERE idReport=49;
DELETE FROM `${prefix}favoriteparameter` WHERE idReport=7;

DELETE FROM `${prefix}habilitationreport` WHERE idReport=49;
DELETE FROM `${prefix}habilitationreport` WHERE idReport=7;

DELETE FROM `${prefix}modulereport` WHERE idReport=49;
DELETE FROM `${prefix}modulereport` WHERE idReport=7;

DELETE FROM `${prefix}navigation` WHERE idReport=49;
DELETE FROM `${prefix}navigation` WHERE idReport=7;

DELETE FROM `${prefix}reportparameter` WHERE idReport=49;
DELETE FROM `${prefix}reportparameter` WHERE idReport=7;

DELETE FROM `${prefix}todayparameter` WHERE idReport=49;
DELETE FROM `${prefix}todayparameter` WHERE idReport=7;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`) VALUES 
(300, 'menuSubscription', 0, 'item', 1280,  null, 0, 'Admin', 1);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,300,1);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(391, 'menuSubscription', 0, 300, 0, 900, null);

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronSubscriptionUpdateRevision');

CREATE TABLE `${prefix}revisionupdate` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`revisionId` varchar(100) DEFAULT NULL,
`version` varchar(100) DEFAULT NULL,
`date` datetime DEFAULT NULL,
`files` varchar(4000) DEFAULT NULL,
`tickets` varchar(4000) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}votingitem`
ADD `nbVoted` int(5) DEFAULT NULL COMMENT '5';


-- CRM Prospect

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(398, 'navCrmProspect', 0, 0, 0, 85,'moduleCrmProspect');
INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`,`parentActive`,`notActiveAlone`) VALUES 
(35,'moduleCrmProspect',990,null,0,0,0,0);



--Prospect

CREATE TABLE `${prefix}prospect` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL, 
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`prospectNameContact` varchar(100) DEFAULT NULL, 
`prospectNameCompany` varchar(100) DEFAULT NULL,
`idProspectType` int(12) unsigned DEFAULT NULL COMMENT '12',
`idProspectOrigin` int(12) unsigned DEFAULT NULL COMMENT '12',
`idDomainProspect` int(12) unsigned DEFAULT NULL COMMENT '12',
`prospectFunction` varchar(100) DEFAULT NULL,
`idPositionProspect` int(12) unsigned DEFAULT NULL COMMENT '12',
`idDecisionMakerProspect` int(12) unsigned DEFAULT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
`email` varchar(100) DEFAULT NULL,
`designation` varchar(100) DEFAULT NULL,
`street` varchar(100) DEFAULT NULL,
`complement` varchar(100) DEFAULT NULL,
`zip` varchar(100) DEFAULT NULL,
`city` varchar(100) DEFAULT NULL,
`state` varchar(100) DEFAULT NULL,
`country` varchar(100) DEFAULT NULL,
`phone` varchar(100) DEFAULT NULL,
`mobile` varchar(100) DEFAULT NULL,
`fax` varchar(100) DEFAULT NULL,
`networkLink` varchar(100) DEFAULT NULL,
`idStatus` int(12) unsigned NOT NULL COMMENT '12',
`lastEventDatetime` datetime, 
`toBeRecontacted` datetime,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(301, 'menuProspect', 7, 'object', 141, 'Project', 0, 'Followup',0),
(302, 'menuProspectType', 79, 'object', 1053, 'ReadWriteType', 0, 'Followup',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(392, 'menuProspect',398,301,0,300,'moduleCrmProspect'),
(393, 'menuProspectType',398,302,0,911,'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 301, 1),
(2, 301, 1),
(3, 301, 1),
(4, 301, 1),
(1, 302, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 301, 8),
(2, 301, 2),
(3, 301, 7),
(4, 301, 1),
(1, 302, 1000001);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('Prospect', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('Prospect', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('Prospect',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('Prospect', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('Prospect', '0');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('Prospect', 'buisiness show', 10, 1, 0),
('Prospect', 'emailing', 20, 1, 0),
('Prospect', 'direct', 30, 1, 0),
('Prospect', 'sponsorship', 40, 1, 0),
('Prospect', 'unknown', 90, 1, 0);


--DomainProspect

CREATE TABLE `${prefix}domainprospect` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL, 
`sortOrder` int(12) unsigned NOT NULL COMMENT '12',
`isPublic` int(1) unsigned DEFAULT '0' COMMENT '1',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(303, 'menuDomainProspect', 7, 'object', 143, 'Project', 0, 'Followup',0);


INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(394, 'menuDomainProspect',398,303,0,306,'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 303, 1),
(2, 303, 1),
(3, 303, 1),
(4, 303, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 303, 8),
(2, 303, 2),
(3, 303, 7),
(4, 303, 1);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('DomainProspect', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('DomainProspect', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('DomainProspect',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('DomainProspect', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('DomainProspect', '0');

INSERT INTO  `${prefix}domainprospect` (`name`, `sortOrder`) VALUES
('Agri-food',110),
('Finance',120),
('Industry',130),
('Construction',140),
('Chemistry',150),
('Trade',160),
('Transportation',170),
('Communication',180),
('Information Technology',190),
('Services',200),
('Education',910),
('Ministry',920),
('Local public establishment',930),
('Public establishment other',940);


--PositionProspect

CREATE TABLE `${prefix}positionprospect` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL, 
`sortOrder` int(12) unsigned NOT NULL COMMENT '12',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(304, 'menuPositionProspect', 7, 'object', 144, 'Project', 0, 'Followup',0);


INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(395, 'menuPositionProspect',398,304,0,307,'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 304, 1),
(2, 304, 1),
(3, 304, 1),
(4, 304, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 304, 8),
(2, 304, 2),
(3, 304, 7),
(4, 304, 1);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('PositionProspect', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('PositionProspect', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('PositionProspect',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('PositionProspect', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('PositionProspect', '0');

INSERT INTO `${prefix}positionprospect` (`id`,`idUser`,`name`,`sortOrder`,`idle`) VALUES 
('1','1','CEO / Director','10','0'),
('2','1','CTO / IT Director','20','0'),
('3','1','Project Manager','30','0'),
('4','1','Project Leader','40','0'),
('5','1','Other','50','0');


--DecisionMakerProspect

CREATE TABLE `${prefix}decisionmakerprospect` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL, 
`sortOrder` int(12) unsigned NOT NULL COMMENT '12',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(305, 'menuDecisionMakerProspect', 7, 'object', 147, 'Project', 0, 'Followup',0);


INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(396, 'menuDecisionMakerProspect',398,305,0,308,'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 305, 1),
(2, 305, 1),
(3, 305, 1),
(4, 305, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 305, 8),
(2, 305, 2),
(3, 305, 7),
(4, 305, 1);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('DecisionMakerProspect', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('DecisionMakerProspect', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('DecisionMakerProspect',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('DecisionMakerProspect', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('DecisionMakerProspect', '0');

INSERT INTO `${prefix}decisionmakerprospect` (`id`,`idUser`,`name`,`sortOrder`,`idle`) VALUES 
(1,1,'Main decision maker','10','0'),
(2,1,'Collective decision maker','20','0'),
(3,1,'Prescriber','30','0'),
(4,1,'Non-decision maker','90','0');


--ProspectOrigin

CREATE TABLE `${prefix}prospectorigin` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`sortOrder` int(12) unsigned NOT NULL COMMENT '12',
`date` datetime,
`idProspectType` int(12) unsigned DEFAULT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(306, 'menuProspectOrigin', 7, 'object', 149, 'Project', 0, 'Followup',0);


INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(397, 'menuProspectOrigin',398,306,0,301,'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 306, 1),
(2, 306, 1),
(3, 306, 1),
(4, 306, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 306, 8),
(2, 306, 2),
(3, 306, 7),
(4, 306, 1);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ProspectOrigin', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('ProspectOrigin', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('ProspectOrigin',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('ProspectOrigin', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('ProspectOrigin', '0');

--ProspectEvent

CREATE TABLE `${prefix}prospectevent` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`idProspect` int(12) unsigned DEFAULT NULL COMMENT '12',
`eventDateTime` datetime,
`name` varchar(100) DEFAULT NULL,
`idProspectEventType` int(12) unsigned DEFAULT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(307, 'menuProspectEvent', 7, 'object', 139, 'Project', 0, 'Followup',0),
(308, 'menuProspectEventType', 79, 'object', 1054, 'ReadWriteType', 0, 'Followup',0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 307, 1),
(2, 307, 1),
(3, 307, 1),
(4, 307, 1),
(1, 308, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 307, 8),
(2, 307, 2),
(3, 307, 7),
(4, 307, 1),
(1, 308, 1000001);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ProspectEvent', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('ProspectEvent', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('ProspectEvent',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('ProspectEvent', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('ProspectEvent', '0');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('ProspectEvent', 'phone call', 10, 1, 0),
('ProspectEvent', 'email', 20, 1, 0),
('ProspectEvent', 'meeting', 30, 1, 0),
('ProspectEvent', 'buisiness show', 40, 1, 0),
('ProspectEvent', 'import', 90, 1, 0); 

-- New planningMode - START

INSERT INTO `${prefix}planningmode` (`id`, `applyTo`, `name`, `code`, `sortOrder`, `idle`, `mandatoryStartDate`, `mandatoryEndDate`) VALUES
(29, 'Activity', 'PlanningModeCDUR', 'CDUR', 340, 1 , 0, 0),
(30, 'TestSession', 'PlanningModeCDUR','CDUR', 340, 1 , 0, 0);

UPDATE `${prefix}planningmode` SET sortOrder=320 WHERE `code`='DDUR';

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(309, 'menuPlanningMode', 36, 'object', 812, 'ReadWriteList', 0, 'ListOfValues',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(401, 'menuPlanningMode',131,309, 0,50,'modulePlanning');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 309, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 309, 1000001);

ALTER TABLE `${prefix}planningelement` 
ADD COLUMN `inheritedStartDate` date DEFAULT NULL;

ALTER TABLE `${prefix}planningelementbaseline` 
ADD COLUMN `inheritedStartDate` date DEFAULT NULL;

-- New planningMode - END

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(233,35,301,0,0),
(234,35,303,0,0),
(235,35,304,0,0),
(236,35,305,0,0),
(237,35,306,0,0),
(238,35,307,0,0),
(239,35,302,0,0);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`) VALUES
('144', 'reportPlanColoredMonthlySameScale', '2', 'colorPlan.php?scale=same', '300');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES
(144, 'month', 'month', '10', '0', 'currentMonth', '0', '0'),
(144, 'idOrganization','organizationList','3','0',NULL, '0','0'),
(144, 'showAdminProj','boolean','60','0',NULL, '0','0'),
(144, 'includeNextMonth','boolean','50','0',NULL, '0','0'),
(144, 'idTeam','teamList','5','0',NULL, '0','0'),
(144, 'idProject','projectList','1','0','currentProject', '0','0');

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
('1', '144', '1');

--AccessSpe set to yes for admin in voting display

INSERT INTO `${prefix}habilitationother` (idProfile, rightAccess, scope) VALUES
(1,1,'nameVoterDetail'),
(1,1,'votingPanelDetail');
