-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.4.0                                      //
-- // Date : 2024-08-05                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V11.4

-- Extend size for costs and amounts
ALTER TABLE `${prefix}budgetelement` CHANGE `budgetCost` `budgetCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `validatedCost` `validatedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `assignedCost` `assignedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `realCost` `realCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `leftCost` `leftCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `plannedCost` `plannedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `progress` `progress` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expenseBudgetAmount` `expenseBudgetAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expenseAssignedAmount` `expenseAssignedAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expensePlannedAmount` `expensePlannedAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expenseRealAmount` `expenseRealAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expenseLeftAmount` `expenseLeftAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `expenseValidatedAmount` `expenseValidatedAmount` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalBudgetCost` `totalBudgetCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalAssignedCost` `totalAssignedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalPlannedCost` `totalPlannedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalRealCost` `totalRealCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalLeftCost` `totalLeftCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `totalValidatedCost` `totalValidatedCost` decimal(14,2) DEFAULT NULL;
ALTER TABLE `${prefix}budgetelement` CHANGE `reserveAmount` `reserveAmount` decimal(14,2) DEFAULT NULL;

-- Organization code on reference
ALTER TABLE `${prefix}organization` ADD `organizationCode` varchar(25) DEFAULT NULL;

-- Phases on Work Unit Catalog
CREATE TABLE `${prefix}workunitcatalogphase` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idCatalogUO` int(12) unsigned DEFAULT NULL COMMENT '12',
  `reference` varchar(200) DEFAULT NULL,
  `ratioPct` int(3) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}workunit` ADD COLUMN `idProject` int(12) unsigned DEFAULT NULL COMMENT '12';
UPDATE `${prefix}workunit` set `idProject`=(select idProject from `${prefix}cataloguo` c where c.id=`${prefix}workunit`.idCatalogUO  ) where idProject is null;

-- Fix comment on Lessons learned

ALTER TABLE `${prefix}lessonlearned` CHANGE `idProject` `idProject` int(12) unsigned DEFAULT NULL COMMENT '12';

-- Work Command : prepare requirements for new screen

ALTER TABLE `${prefix}workcommand` ADD COLUMN `idle` int(1) unsigned DEFAULT '0';

ALTER TABLE `${prefix}workcommand` ADD COLUMN `idProject` int(12) unsigned DEFAULT NULL COMMENT '12';
UPDATE `${prefix}workcommand` set `idProject`=(select idProject from `${prefix}workunit` wu where wu.id=`${prefix}workcommand`.idWorkUnit  ) where idProject is null;

CREATE TABLE `${prefix}acceptance` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `externalReference` varchar(100) DEFAULT NULL,
  `idAcceptanceType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `description` mediumtext DEFAULT NULL,
  `result` mediumtext DEFAULT NULL,
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `acceptanceDate` date DEFAULT NULL,
  `handled` INT(1) UNSIGNED DEFAULT '0' COMMENT '1',
  `handledDateTime` DATETIME DEFAULT NULL,
  `done` INT(1) UNSIGNED DEFAULT '0' COMMENT '1',
  `doneDateTime` DATETIME DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  `idleDateTime` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `acceptanceAcceptanceTypeIdx` ON `${prefix}acceptance` (`idAcceptanceType`);

INSERT INTO `${prefix}menu` (`id`,`name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(311,'menuAcceptance', 6, 'object', 378, null, 1, 'Work Meeting'),
(312,'menuAcceptanceType', 79, 'object', 1055, 'ReadWriteType', 1, 'Type');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1, 311, 1),
(2, 311, 1),
(3, 311, 1),
(1, 312, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(1, 311, 8),
(2, 311, 2),
(3, 311, 7),
(1, 312, 8);

-- INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
-- (405,'menuAcceptance',5,311,65,0),
-- (406,'menuAcceptanceType',330,312,296,0);

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idle`, `code`) VALUES 
('Acceptance', 'partial', '10',1,'PART'),
('Acceptance', 'total', '20',1,'ALL');

CREATE TABLE `${prefix}workcommandaccepted` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idWorkCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `acceptedQuantity` decimal(8,3) DEFAULT NULL,
  `idActivityWorkUnit` int(12) unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

-- ALTER TABLE `${prefix}workcommand`
-- ADD `acceptedQuantity` DECIMAL(8,3) NULL DEFAULT NULL AFTER `billedAmount`,
-- ADD `acceptedAmount` DECIMAL(14,2) NULL DEFAULT NULL AFTER `acceptedQuantity`;