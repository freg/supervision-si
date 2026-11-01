-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.3.0                                       //
-- // Date : 2022-12-21                                    //
-- ///////////////////////////////////////////////////////////

-- Activity expense 

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES 
(287, 'menuActivityExpense', 151, 'object', 215,  'Project', 0, 'Work Financial'),
(288, 'menuActivityExpenseType', 79, 'object', 940, 'ReadWriteType', 0, 'Type');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idle`, `color`, idWorkflow) VALUES ('ActivityExpense', 'Expense activity', 10, 0, NULL, 8);
INSERT INTO `${prefix}originable` (`id`, `name`, `idle`) VALUES (35, 'ActivityExpense', 0);
INSERT INTO `${prefix}copyable` (`id`, `name`, `idle`, `sortOrder`) VALUES (33, 'IndividualExpense', 0, 55);
INSERT INTO `${prefix}referencable` (`id`, `name`, `idle`) VALUES (29, 'ActivityExpense', 0);
INSERT INTO `${prefix}importable` (`id`, `name`, `idle`) VALUES (73, 'ActivityExpense', 0);
INSERT INTO `${prefix}textable` (`id`,`name`,`idle`) VALUES (46,'ActivityExpense',0);
INSERT INTO `${prefix}linkable` (`id`,`name`,`idle`, idDefaultLinkable) VALUES (41,'ActivityExpense',0,null);
INSERT INTO `${prefix}mailable` (id, name, idle) VALUES (50, 'ActivityExpense', 0);
INSERT INTO `${prefix}indicatorable` (`id`,`name`, `idle`) VALUES (25,'IndividualExpense', '0');
INSERT INTO `${prefix}indicatorableindicator` (`idIndicatorable`, `nameIndicatorable`, `idIndicator`, `idle`) VALUES ('82', 'ActivityExpense', '25', '0');
INSERT INTO `${prefix}checklistable` (`id`,`name`, `idle`) VALUES (40,'ActivityExpense', '0');

UPDATE `${prefix}navigation` SET id=100012001 WHERE name='menuImportProject';
UPDATE `${prefix}navigation` SET id=378 WHERE name='menuCriticalResources' and id>378; 
UPDATE `${prefix}navigation` SET id=379 WHERE name='menuResourceMaterial' and id>379; 
UPDATE `${prefix}navigation` SET id=380 WHERE name='menuAssignment' and id>380; 
INSERT INTO `${prefix}navigation` (`id`,`name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(381, 'menuActivityExpense',13,287,25,0),
(382, 'menuActivityExpenseType',328,288,25,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,287,1),
(3,287,1), 
(1,288,1),
(3,288,1);  

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(1,287, 8),
(3,287, 7),
(1,288, 8),
(3,288, 7);

ALTER TABLE `${prefix}expense` ADD idActivity int(12) DEFAULT NULL;

ALTER TABLE `${prefix}expensedetailtype` ADD `activity` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}expensedetail` ADD `idActivity` int(12) unsigned COMMENT '12';

CREATE TABLE `${prefix}timeline` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,  
`idUser` int(12) unsigned NOT NULL COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

-- CRITICAL RESOURCES SCENARIO
CREATE TABLE `${prefix}criticalresourcescenarioproject` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idProject` int(12) unsigned COMMENT '12',
`idUser` int(12) unsigned COMMENT '12',
`idScenario` int(12) unsigned COMMENT '12',
`proposale` int(1) unsigned COMMENT '1',
`monthDelay` int(3) COMMENT '3',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX criticalresourcescenarioprojectuserproject ON `${prefix}criticalresourcescenarioproject` (`idUser`,`idProject`);
CREATE INDEX criticalresourcescenarioprojectuserscenario ON `${prefix}criticalresourcescenarioproject` (`idUser`,`idScenario`);

CREATE TABLE `${prefix}criticalresourcescenariopool` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idResource` int(12) unsigned COMMENT '12',
`idUser` int(12) unsigned COMMENT '12',
`idScenario` int(12) unsigned COMMENT '12',
`extracapacity` DECIMAL(5,2),
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX criticalresourcescenariopooluserresource ON `${prefix}criticalresourcescenariopool` (`idUser`,`idResource`);
CREATE INDEX criticalresourcescenariopooluserscenario ON `${prefix}criticalresourcescenariopool` (`idUser`,`idScenario`);

CREATE TABLE `${prefix}criticalresourcescenario` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100),
`idUser` int(12) unsigned COMMENT '12',
`creationDate` date,
`lastUpdateDate` date,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}role` ADD `defaultExternalCost` DECIMAL(9,2) DEFAULT NULL;

DELETE FROM `${prefix}notifiable` WHERE id=31;
UPDATE `${prefix}notifiable` SET name=notifiableItem WHERE id in (32,35);
DELETE FROM `${prefix}notifiable` WHERE notifiableItem like '%Leave%' and notifiableItem!=name;

-- FIX FOR 10.4.3 THAT HAS NOT ITS PLACE IN PATCH V10.4.3. AS VALUES MAY ALREADY BE SAVED
INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(2,287, 2),
(4,287, 9),
(5,287, 9),
(6,287, 9),
(7,287, 9);