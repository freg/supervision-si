-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 13.1.0                                      //
-- ///////////////////////////////////////////////////////////

-- Mandatory note when changing to a configured status (Activity, Ticket, Action types)
ALTER TABLE `${prefix}type` ADD `mandatoryNoteOnStatusChange` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}type` ADD `idStatusMandatoryNote` int(12) unsigned DEFAULT NULL COMMENT '12';

-- Source of inherited planning dates
ALTER TABLE `${prefix}planningelement` ADD `inheritedStartSource` varchar(150) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD `inheritedEndSource` varchar(150) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD `inheritedStartSource` varchar(150) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD `inheritedEndSource` varchar(150) DEFAULT NULL;


-- ============================================================
-- RACI
-- ============================================================

CREATE TABLE `${prefix}racimodel` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) DEFAULT NULL COMMENT '5',
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}racifunction` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idRaciModel` int(12) unsigned DEFAULT NULL COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) DEFAULT NULL COMMENT '5',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_racifunction_model` ON `${prefix}racifunction` (`idRaciModel`);

CREATE TABLE `${prefix}racirole` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idRaciModel` int(12) unsigned DEFAULT NULL COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) DEFAULT NULL COMMENT '5',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_racirole_model` ON `${prefix}racirole` (`idRaciModel`);
CREATE TABLE `${prefix}racicell` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idRaciModel` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idRaciFunction` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idRaciRole` int(12) unsigned DEFAULT NULL COMMENT '12',
  `value` varchar(1) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_racicell_model` ON `${prefix}racicell` (`idRaciModel`);
CREATE INDEX `idx_racicell_function` ON `${prefix}racicell` (`idRaciFunction`);
CREATE INDEX `idx_racicell_role` ON `${prefix}racicell` (`idRaciRole`);

CREATE TABLE `${prefix}raciassignment` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idRaciModel` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idRaciRole` int(12) unsigned DEFAULT NULL COMMENT '12',
  `resourceType` varchar(20) DEFAULT NULL,
  `resourceId` int(12) unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_raciassignment_project` ON `${prefix}raciassignment` (`idProject`);
CREATE INDEX `idx_raciassignment_model` ON `${prefix}raciassignment` (`idRaciModel`);
CREATE INDEX `idx_raciassignment_role` ON `${prefix}raciassignment` (`idRaciRole`);

ALTER TABLE `${prefix}project` ADD `idRaciModel` int(12) DEFAULT NULL COMMENT '12';
CREATE INDEX `idx_project_racimodel` ON `${prefix}project` (`idRaciModel`);

-- ============================================================
-- RACI screen registration (menuRaciModel)
-- ============================================================
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(380,'menuRaciModel', 88, 'object', 3870, 'ReadWriteAutomation', 0, 'Automation');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`, `moduleName`) VALUES
(434, 'menuRaciModel',5,380,0,65,'');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 380, 1),
(2, 380, 1),
(3, 380, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 380, 1000001);
INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `id`, 380, 1000002 FROM `${prefix}profile` WHERE `id`!=1;

-- ============================================================
-- Yearly colored planning report
-- ============================================================
INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `idle`, `orientation`, `hasCsv`, `hasView`, `hasPrint`, `hasPdf`, `hasToday`, `hasFavorite`, `hasWord`, `hasExcel`, `filterClass`, `referTo`) VALUES
(148, 'reportPlanColoredYearly', 2, 'colorPlan.php', 285, 0, 'L', 0, 1, 1, 1, 1, 1, 0, 0, NULL, NULL);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES
(148, 'idProject', 'projectList', 1, 0, 'currentProject', 0, 0),
(148, 'idOrganization', 'organizationList', 3, 0, NULL, 0, 0),
(148, 'idTeam', 'teamList', 5, 0, NULL, 0, 0),
(148, 'yearNoMonthStart', 'year', 10, 0, 'currentYear', 0, 0),
(148, 'showAdminProj', 'boolean', 60, 0, '0', 0, 0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES
(1, 148, 1),
(2, 148, 1),
(3, 148, 1),
(4, 148, 0),
(5, 148, 0),
(6, 148, 0),
(7, 148, 0);


-- Dependency `idle`
ALTER TABLE `${prefix}dependency` ADD COLUMN `idle` int(1) unsigned DEFAULT '0' COMMENT '1';

-- Remove Input MailBox parameters
DELETE FROM `${prefix}parameter` WHERE parameterCode IN ('cronCheckEmailsHost','cronCheckEmailsUser','cronCheckEmailsPassword','afterMailTreatment','allowAttachInputMails','sizeAttachmentInputMails');

-- Input Mailbox for tickets : when note is received on closed item, reopen it
ALTER TABLE `${prefix}inputmailboxticket` ADD COLUMN `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}inputmailboxticket` ADD COLUMN `reopenCondition` varchar(10) DEFAULT 'IDLE';

-- ============================================================
-- New screen : document explorer
-- ============================================================

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`) VALUES
(381, 'menuDocumentExplorer', 0, 'item', 65, 'Project', 0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `sortOrder`, `idReport`) VALUES
(435, 'menuDocumentExplorer', 7, 381, 15, 0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 381, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 102;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 381, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 102;

-- ============================================================
-- One-time password authentication
-- ============================================================
CREATE TABLE `${prefix}otprequest` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idUser` int(12) unsigned NOT NULL COMMENT '12',
  `requestDateTime` datetime NOT NULL,
  `codeHash` varchar(255) NOT NULL,
  `used` int(1) unsigned NOT NULL DEFAULT 0 COMMENT '1',
  `validationTry` int(3) unsigned NOT NULL DEFAULT 0 COMMENT '3',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_otprequest_user_date` ON `${prefix}otprequest` (`idUser`, `requestDateTime`);

INSERT INTO `${prefix}parameter` (`idUser`, `parameterCode`, `parameterValue`) VALUES
(null, 'otpForAdminUsers', 'NO'),
(null, 'otpForNewUsers', 'NO'),
(null, 'otpForDirectConnectionsWithSso', 'NO');

-- Add on hold status on Todo Lists
ALTER TABLE `${prefix}subtask` ADD `paused` int(1) unsigned DEFAULT 0 COMMENT '1';

-- ============================================================
-- ProspectEstimate : table
-- ============================================================
CREATE TABLE `${prefix}prospectestimate` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProspectEstimateType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProspect` int(12) unsigned DEFAULT NULL COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `description` longtext DEFAULT NULL,
  `creationDate` date DEFAULT NULL,
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `additionalInfo` longtext DEFAULT NULL,
  `initialEndDate` date DEFAULT NULL,
  `untaxedAmount` decimal(12,2) DEFAULT NULL,
  `initialPricePerDayAmount` decimal(12,2) DEFAULT '0.00',
  `initialAmount` decimal(12,2) DEFAULT '0.00',
  `comment` longtext DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  `done` int(1) unsigned DEFAULT '0' COMMENT '1',
  `cancelled` int(1) unsigned DEFAULT '0' COMMENT '1',
  `idleDate` date DEFAULT NULL,
  `doneDate` date DEFAULT NULL,
  `handled` int(1) unsigned DEFAULT '0' COMMENT '1',
  `handledDate` date DEFAULT NULL,
  `reference` varchar(100) DEFAULT NULL,
  `result` longtext DEFAULT NULL,
  `tax` decimal(5,2) DEFAULT NULL,
  `fullAmount` decimal(12,2) DEFAULT NULL,
  `idLikelihood` int(12) unsigned DEFAULT NULL COMMENT '12',
  `plannedWork` decimal(12,2) DEFAULT '0.00',
  `fullAmountLocal` decimal(12,2) DEFAULT NULL,
  `initialAmountLocal` decimal(12,2) DEFAULT NULL,
  `initialPricePerDayAmountLocal` decimal(12,2) DEFAULT NULL,
  `untaxedAmountLocal` decimal(12,2) DEFAULT NULL,
  `taxAmountLocal` decimal(11,2) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE INDEX prospectEstimateProject ON `${prefix}prospectestimate` (idProject);
CREATE INDEX prospectEstimateUser ON `${prefix}prospectestimate` (idUser);
CREATE INDEX prospectEstimateResource ON `${prefix}prospectestimate` (idResource);
CREATE INDEX prospectEstimateStatus ON `${prefix}prospectestimate` (idStatus);
CREATE INDEX prospectEstimateType ON `${prefix}prospectestimate` (idProspectEstimateType);
CREATE INDEX prospectEstimateProspect ON `${prefix}prospectestimate` (idProspect);

-- ============================================================
-- ProspectEstimate : types par defaut
-- ============================================================
INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idle`, `idWorkflow`, `mandatoryDescription`, `mandatoryResultOnDone`, `mandatoryResourceOnHandled`, `lockHandled`, `lockDone`, `lockIdle`, `code`) VALUES 
('ProspectEstimate', 'Fixed Price', '10', '0', '1', '0', '0', '0', '0', '1', '1', ''),
('ProspectEstimate', 'Per day', '20', '0', '1', '0', '0', '0', '0', '1', '1', ''),
('ProspectEstimate', 'Per month', '30', '0', '1', '0', '0', '0', '0', '1', '1', ''),
('ProspectEstimate', 'Per year', '40', '0', '1', '0', '0', '0', '0', '1', '1', '');

-- ============================================================
-- ProspectEstimate : ecran
-- ============================================================
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(382, 'menuProspectEstimate', 7, 'object', 706, 'Project', 0, 'Financial'),
(383, 'menuProspectEstimateType', 79, 'object', 5266, 'ReadWriteType', 0, 'Followup');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(436, 'menuProspectEstimate', 398, 382, 0, 305, 'moduleCrmProspect'),
(437, 'menuProspectEstimateType', 398, 383, 0, 915, 'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 382, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 131;
INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 383, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 132;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `idProfile`, 382, `idAccessProfile` FROM `${prefix}accessright` WHERE `idMenu` = 131;
INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `idProfile`, 383, `idAccessProfile` FROM `${prefix}accessright` WHERE `idMenu` = 132;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 382, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 301;
INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 383, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 302;

-- ============================================================
-- ProspectEstimate : capacites
-- ============================================================
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}copyable` (`name`, `idle`, `sortOrder`, `idDefaultCopyable`) VALUES ('ProspectEstimate', 0, 39, 14);
INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}indicatorable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}linkable` (`name`, `idle`, `idDefaultLinkable`) VALUES ('ProspectEstimate', 0, 45);
INSERT INTO `${prefix}mailable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}notifiable` (`notifiableItem`, `name`, `idle`) VALUES ('ProspectEstimate', 'ProspectEstimate', 0);
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}referencable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);
INSERT INTO `${prefix}textable` (`name`, `idle`) VALUES ('ProspectEstimate', 0);

-- ============================================================
-- ProspectQualification : table
-- ============================================================
CREATE TABLE `${prefix}prospectqualification` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) unsigned DEFAULT NULL COMMENT '5',
  `description` mediumtext DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}prospectqualification` (`name`, `sortOrder`) VALUES
('Prospect', 10),
('Prospect client', 20),
('Partenaire', 30),
('Partenaire et prospect', 40),
('Simple utilisateur', 50);

-- ============================================================
-- ProspectQualification : ecran
-- ============================================================
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(384, 'menuProspectQualification', 7, 'object', 740, 'ReadWriteList', 0, 'Followup');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(438, 'menuProspectQualification', 398, 384, 0, 309, 'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 384, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 303;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `idProfile`, 384, `idAccessProfile` FROM `${prefix}accessright` WHERE `idMenu` = 303;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 384, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 303;

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ProspectQualification', 0);

-- ============================================================
-- ProspectQualification : champ sur Client, Contact et Prospect
-- ============================================================
ALTER TABLE `${prefix}client` ADD COLUMN `idProspectQualification` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}resource` ADD COLUMN `idProspectQualification` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}prospect` ADD COLUMN `idProspectQualification` int(12) unsigned DEFAULT NULL COMMENT '12';

-- ============================================================
-- Engagement : table
-- ============================================================
CREATE TABLE `${prefix}engagement` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) unsigned DEFAULT NULL COMMENT '5',
  `description` mediumtext DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}engagement` (`name`, `sortOrder`) VALUES
('Bouillant', 10),
('Chaud', 20),
('Tiède', 30),
('Froid', 40),
('Neutre', 50);

-- ============================================================
-- Engagement : ecran
-- ============================================================
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(385, 'menuEngagement', 7, 'object', 742, 'ReadWriteList', 0, 'Followup');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(439, 'menuEngagement', 398, 385, 0, 310, 'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 385, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 384;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `idProfile`, 385, `idAccessProfile` FROM `${prefix}accessright` WHERE `idMenu` = 384;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 385, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 384;

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('Engagement', 0);

-- ============================================================
-- Champs de qualification sur Prospect et Client
-- ============================================================
ALTER TABLE `${prefix}prospect` ADD COLUMN `idLanguage` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}prospect` ADD COLUMN `idEngagement` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}client` ADD COLUMN `idDomainProspect` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}client` ADD COLUMN `idLanguage` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}client` ADD COLUMN `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}client` ADD COLUMN `idResource` int(12) unsigned DEFAULT NULL COMMENT '12';

-- ============================================================
-- idProspectType devient idProspectionSource
-- ============================================================
UPDATE `${prefix}type` SET `scope`='ProspectionSource' WHERE `scope`='Prospect';

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idle`, `idWorkflow`, `mandatoryDescription`, `mandatoryResultOnDone`, `mandatoryResourceOnHandled`, `lockHandled`, `lockDone`, `lockIdle`, `code`) VALUES
('Prospect', 'Prospect', '10', '0', '1', '0', '0', '0', '0', '0', '0', '');

ALTER TABLE `${prefix}prospect` CHANGE `idProspectType` `idProspectionSource` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}prospect` ADD COLUMN `idProspectType` int(12) unsigned DEFAULT NULL COMMENT '12';

UPDATE `${prefix}prospect` SET `idProspectType` = (SELECT `id` FROM `${prefix}type` WHERE `scope`='Prospect' AND `name`='Prospect');

-- ============================================================
-- Le menu 302 devient la source, un nouveau menu porte le type
-- ============================================================
UPDATE `${prefix}menu` SET `name`='menuProspectionSource' WHERE `id`=302;
UPDATE `${prefix}navigation` SET `name`='menuProspectionSource' WHERE `id`=393;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(386, 'menuProspectType', 79, 'object', 5266, 'ReadWriteType', 0, 'Followup');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(440, 'menuProspectType', 398, 386, 0, 912, 'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 386, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 302;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`)
SELECT `idProfile`, 386, `idAccessProfile` FROM `${prefix}accessright` WHERE `idMenu` = 302;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 386, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 302;

-- ============================================================
-- prospectorigin suit le renommage
-- ============================================================
ALTER TABLE `${prefix}prospectorigin` CHANGE `idProspectType` `idProspectionSource` int(12) unsigned DEFAULT NULL COMMENT '12';

-- ============================================================
-- ProspectionSource sort de la table type
-- ============================================================
CREATE TABLE `${prefix}prospectionsource` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `sortOrder` int(5) unsigned DEFAULT NULL COMMENT '5',
  `description` mediumtext DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}prospectionsource` (`id`, `name`, `sortOrder`, `idle`, `description`)
SELECT `id`, `name`, `sortOrder`, `idle`, `description` FROM `${prefix}type` WHERE `scope`='ProspectionSource';

DELETE FROM `${prefix}type` WHERE `scope`='ProspectionSource';

-- ============================================================
-- ProspectionSource : le menu passe de type a liste de valeurs
-- ============================================================
UPDATE `${prefix}menu` SET `idMenu`=7, `sortOrder`=744, `level`='ReadWriteList' WHERE `id`=302;
UPDATE `${prefix}navigation` SET `sortOrder`=302 WHERE `id`=393;

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(2, 302, 1000002),
(3, 302, 1000002),
(4, 302, 1000002);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ProspectionSource', 0);

-- ============================================================
-- ProspectEvent : refType + refId
-- ============================================================
ALTER TABLE `${prefix}prospectevent` ADD COLUMN `refType` varchar(100) DEFAULT NULL;
ALTER TABLE `${prefix}prospectevent` CHANGE `idProspect` `refId` int(12) unsigned DEFAULT NULL COMMENT '12';

UPDATE `${prefix}prospectevent` SET `refType`='Prospect';

CREATE INDEX prospectEventRef ON `${prefix}prospectevent` (refType, refId);

-- ============================================================
-- Prospect : responsable
-- ============================================================
ALTER TABLE `${prefix}prospect` ADD COLUMN `idResource` int(12) unsigned DEFAULT NULL COMMENT '12';

-- ============================================================
-- Ecran Prospection view
-- ============================================================
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(387, 'menuProspectionView', 0, 'item', 66, 'Project', 0, NULL);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(441, 'menuProspectionView', 398, 387, 0, 299, 'moduleCrmProspect');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`)
SELECT `idProfile`, 387, `allowAccess` FROM `${prefix}habilitation` WHERE `idMenu` = 301;

INSERT INTO `${prefix}modulemenu` (`idModule`, `idMenu`, `hidden`, `active`)
SELECT `idModule`, 387, `hidden`, `active` FROM `${prefix}modulemenu` WHERE `idMenu` = 301;

-- ============================================================
-- Engagement : couleur
-- ============================================================
ALTER TABLE `${prefix}engagement` ADD COLUMN `color` varchar(7) DEFAULT NULL;

UPDATE `${prefix}engagement` SET `color`='#9932cc' WHERE `id`=1;
UPDATE `${prefix}engagement` SET `color`='#ff4500' WHERE `id`=2;
UPDATE `${prefix}engagement` SET `color`='#ffe4b5' WHERE `id`=3;
UPDATE `${prefix}engagement` SET `color`='#87cefa' WHERE `id`=4;
UPDATE `${prefix}engagement` SET `color`='#d3d3d3' WHERE `id`=5;
-- fin Engagement : couleur

-- ============================================================
-- ProspectEvent : contact
-- ============================================================
ALTER TABLE `${prefix}prospectevent` ADD COLUMN `idContact` int(12) unsigned DEFAULT NULL COMMENT '12';

CREATE INDEX prospectEventContact ON `${prefix}prospectevent` (idContact);
-- fin ProspectEvent : contact

-- ============================================================
-- Menu gauche : types du CRM dans les listes de types
-- ============================================================
-- Le noeud reprend le nom de la racine CRM : les noms ne sont pas uniques dans
-- cet arbre, et menuNewGuiLeft retombe sur menuCrmProspect pour le libelle.
INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`, `idReport`, `sortOrder`, `moduleName`) VALUES
(442, 'navCrmProspect', 132, 0, 0, 120, 'moduleCrmProspect');

UPDATE `${prefix}navigation` SET `idParent`=442, `sortOrder`=10 WHERE `id`=440;
UPDATE `${prefix}navigation` SET `idParent`=442, `sortOrder`=20 WHERE `id`=437;
UPDATE `${prefix}navigation` SET `idParent`=442, `sortOrder`=30 WHERE `id`=412;
-- fin Menu gauche : types du CRM

-- ============================================================
-- CRON : traitement des consolidations differees (WaitingUpdate)
-- ============================================================
INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle`, `fonctionName`) VALUES
('*/5 * * * *', '../tool/cronExecutionStandard.php', 0, 'cronExecuteWaitingUpdates');
-- fin CRON : traitement des consolidations differees
