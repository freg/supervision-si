-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.1.0                                       //
-- // Date : 2022-07-26                                    //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}leavetype` ADD notRequiredRight int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}leavetypeofemploymentcontracttype` ADD hasNoRight int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}employeeleaveearned` ADD poseWithoutRights int(1) unsigned DEFAULT 0 COMMENT '1';

ALTER TABLE `${prefix}testcaserun`
ADD `idUser` int(12) DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES (33, 'showVAT', 'boolean', 30, 0, 'false', 0,0);
INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES (35, 'showVAT', 'boolean', 30, 0, 'false', 0,0);

INSERT INTO `${prefix}parameter` (`idUser`, `idProject`, `parameterCode`, `parameterValue`) VALUES (Null, Null, 'limitDisplayPlanning', 100);

ALTER TABLE `${prefix}votinguserule` ADD `isDownVoting` int(1) unsigned DEFAULT '0' COMMENT '1';

ALTER TABLE `${prefix}votingitem` CHANGE `actualValue` `actualValue` int(5) COMMENT '5';

ALTER TABLE `${prefix}voting` CHANGE `value` `value` int(5) COMMENT '5';

-- ======================================
-- Create table criticalresources + criticalresourcesProjects to have multiple projects on criticalresources page
-- ======================================

CREATE TABLE `${prefix}criticalresources` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`scale` varchar(10) DEFAULT NULL,
`numberResources` int(5) DEFAULT NULL,
`endDate` date DEFAULT NULL,
`startDate` date DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}criticalresourcesprojects` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`idCriticalResources` int(12) unsigned NOT NULL COMMENT '12',
`idProjet` int(12) unsigned NOT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

-- ======================================
-- Insert criticalresources Into menu 
-- ======================================

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`, `isLeavesSystemMenu`) VALUES
(284, 'menuCriticalResources', 7, 'item', 121, NULL, 0, 'Work', 0, 0);

UPDATE `${prefix}menu` SET `sortOrder` = 122 WHERE id = 252;
UPDATE `${prefix}menu` SET `sortOrder` = 123 WHERE id = 257;

-- ======================================
-- Insert criticalresources Into Navigation 
-- ======================================
UPDATE `${prefix}navigation` SET id=100012001 WHERE name='menuImportProject';
INSERT INTO `${prefix}navigation` (`id`,`name`, `idParent`, `idMenu`, `sortOrder`, `idReport`, `tag`, `moduleName`) VALUES
(378,'menuCriticalResources', 1, 284, 75,0, NULL, NULL);

-- ======================================
-- Insert criticalresources Into habilitation 
-- ======================================

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1, 284, 1),
(2, 284, 1),
(3, 284, 1),
(4, 284, 1),
(5, 284, 1),
(6, 284, 1),
(7, 284, 1);

UPDATE `${prefix}report` SET `file` = 'expensePlan.php?scale=month&scope=Project&showVAT=false' WHERE `id` = 33;
UPDATE `${prefix}report` SET `file` = 'expensePlan.php?scale=month&scope=Individual&showVAT=false' WHERE `id` = 34;
UPDATE `${prefix}report` SET `file` = 'expensePlan.php?scale=month&showVAT=false' WHERE `id` = 35;

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`, `referTo`) VALUES
(132, 'reportResourcePlan',2, 'resourcePlanReport.php', 228,'1', 'synthesisWork');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `multiple`, `required`) VALUES 
(132, 'idProject', 'projectList', 10, 'currentProject',0,0),
(132,'showIdle','boolean',25,null,0,0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 132, 1),
(2, 132, 1),
(3, 132, 1);

INSERT INTO `${prefix}parameter` (`idUser`, `idProject`, `parameterCode`, `parameterValue`) VALUES (Null, Null, 'limitDisplayPlanning', 100);

UPDATE `${prefix}report` SET `hasExcel` = 1 WHERE `id` = 44;

-- Purge Ghost sessions
INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('30 * * * *', '../tool/cronExecutionStandard.php', 0, 'purgeGhostSessions');

-- Fix sortOrder Formating
UPDATE `${prefix}columnselector` SET `formatter`= 'numericFormatter' WHERE `field` = 'sortOrder' and `formatter` is null;

INSERT INTO `${prefix}type` (`scope`, `code`, `name`, `sortOrder`,`idWorkflow` ) VALUES
('Project', 'PRP', 'Proposale', '100', (select min(w.id) from `${prefix}workflow` w));

ALTER TABLE `${prefix}project` 
ADD `strength` mediumtext DEFAULT NULL, 
ADD `weakness` mediumtext DEFAULT NULL,
ADD `opportunity` mediumtext DEFAULT NULL,
ADD `threats` mediumtext DEFAULT NULL,
ADD `strategicvalue` int(10) unsigned DEFAULT NULL COMMENT '10',
ADD `idRiskLevel` int(12) unsigned DEFAULT NULL COMMENT '12',
ADD `benefitValue` int(10) unsigned DEFAULT NULL COMMENT '10';

INSERT INTO `${prefix}report` (`id`,`name`, `idReportCategory`, `file`, `sortOrder`, `idle`, `orientation`, `hasCsv`, `hasView`, `hasPrint`, `hasPdf`, `hasToday`, `hasFavorite`, `hasWord`, `hasExcel`, `filterClass`, `referTo`) 
VALUES (133,'reportWorkLoadHistory',11,'workloadhistory.php',1165,0,'P', 0,1,1,1, 1, 1, 0,0,0,null);
INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 133, 1),
(2, 133, 1),
(3, 133, 1);
INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES (133, 'idProject', 'projectList', 10, 0, 'currentProject', 0,1 );

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`,`hasPdf`,`hasToday`) VALUES (134, 'proposales', 10, 'proposal.php', 1055,0,0,0);
INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES (1, 134, 1);

ALTER TABLE `${prefix}resource` ADD `isMaterial` int(1) UNSIGNED DEFAULT 0 COMMENT '1'; 
ALTER TABLE `${prefix}assignment` ADD `isMaterial` int(1) UNSIGNED DEFAULT 0 COMMENT '1';

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`, `isLeavesSystemMenu`) VALUES
(285,'menuResourceMaterial', 14, 'object', 670, 'ReadWriteEnvironment', 0, 'Work EnvironmentalParameter', 0, 0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,285,1),
(3,285,1);  

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(1,285, 1000001),
(3,285, 1000001);

INSERT INTO `${prefix}navigation` (`id`,`name`, `idParent`, `idMenu`, `sortOrder`, `idReport`, `tag`, `moduleName`) VALUES
(379,'menuResourceMaterial', 128, 285, 45,0, NULL, NULL);
